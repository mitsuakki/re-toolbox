#!/usr/bin/env python3
"""
MCP Gateway — single entry point composing all toolbox MCP servers.

Spawns child MCP servers as subprocesses, proxies all tools/resources/prompts
with namespaced names so Claude Desktop needs only ONE MCP config entry.

Children:
  r2__*      — radare2 analysis (r2mcp via r2pm)
  ghidra__*  — Ghidra headless decompilation (bridge_mcp_ghidra.py)
  shell__*   — arbitrary shell commands

Usage (in container):
  python3 /opt/tools/scripts/mcp/gateway.py

Claude Desktop config (single entry):
  {
    "toolbox": {
      "command": "docker",
      "args": ["exec", "-i", "toolbox", "python3", "/opt/tools/scripts/mcp/gateway.py"]
    }
  }
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession, Server
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    TextContent,
    Tool,
)

# --- Logging to stderr so stdout stays clean for MCP transport -----------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("gateway")


# ===========================================================================
# Child process definitions
# ===========================================================================

@dataclass
class ChildDef:
    namespace: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_connect: float = 15.0  # generous — ghidra bridge can be slow


CHILDREN: list[ChildDef] = [
    ChildDef(
        namespace="r2",
        command="r2pm",
        args=["-r", "r2mcp"],
    ),
    ChildDef(
        namespace="ghidra",
        command="python3",
        args=["/opt/tools/ghidra-mcp/bridge_mcp_ghidra.py"],
        env={"GHIDRA_MCP_URL": os.environ.get("GHIDRA_MCP_URL", "http://127.0.0.1:8089")},
        timeout_connect=20.0,
    ),
    ChildDef(
        namespace="shell",
        command="python3",
        args=["/opt/tools/scripts/mcp/shell-mcp.py"],
    ),
]


# ===========================================================================
# Gateway
# ===========================================================================

class Gateway:
    """Composes child MCP servers behind a single stdio transport."""

    def __init__(self) -> None:
        self.server = Server("toolbox-gateway")
        self._exit_stack = AsyncExitStack()
        self._children: dict[str, ClientSession] = {}
        # namespaced_name -> (namespace, original_name, Tool)
        self._tools: dict[str, tuple[str, str, Tool]] = {}

    # ---- child lifecycle ------------------------------------------------------

    async def _connect_child(self, child: ChildDef) -> ClientSession:
        """Launch child process and return initialized session."""
        env = os.environ.copy()
        env.update(child.env)

        params = StdioServerParameters(
            command=child.command,
            args=child.args,
            env=env,
        )

        transport = await self._exit_stack.enter_async_context(
            stdio_client(params)
        )
        read, write = transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        await session.initialize()
        return session

    async def start(self) -> None:
        """Connect all children and register their tools."""

        for child_def in CHILDREN:
            ns = child_def.namespace
            try:
                log.info("connecting %s MCP (%s %s)…", ns, child_def.command, " ".join(child_def.args))
                session = await asyncio.wait_for(
                    self._connect_child(child_def),
                    timeout=child_def.timeout_connect,
                )
                self._children[ns] = session

                # Enumerate tools
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    ns_name = self._ns_name(ns, tool.name)
                    self._tools[ns_name] = (ns, tool.name, tool)
                    log.info("  tool: %s", ns_name)

                if not tools_result.tools:
                    log.warning("  %s MCP: no tools exposed", ns)

            except asyncio.TimeoutError:
                log.error("%s MCP: connection timed out after %ss — skipped", ns, child_def.timeout_connect)
            except Exception:
                log.exception("%s MCP: failed to start — skipped", ns)

        if not self._children:
            log.error("No child MCPs connected — gateway is empty")

        self._register_handlers()

    # ---- namespacing ----------------------------------------------------------

    @staticmethod
    def _ns_name(ns: str, name: str) -> str:
        return f"{ns}__{name}"

    # ---- handler registration -------------------------------------------------

    def _register_handlers(self) -> None:
        server = self.server

        @server.list_tools()
        async def list_tools() -> list[Tool]:
            tools: list[Tool] = []
            for ns_name, (_ns, _orig, tool) in sorted(self._tools.items()):
                tools.append(Tool(
                    name=ns_name,
                    description=f"[{_ns}] {tool.description or ''}",
                    inputSchema=tool.inputSchema,
                ))
            return tools

        @server.call_tool()
        async def call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent | ImageContent | EmbeddedResource]:
            if name not in self._tools:
                raise ValueError(f"Unknown tool: {name}")

            ns, orig_name, _tool = self._tools[name]
            session = self._children[ns]
            result: CallToolResult = await session.call_tool(orig_name, arguments)
            return result.content

        @server.list_resources()
        async def list_resources():
            resources: list[Any] = []
            for ns, session in sorted(self._children.items()):
                try:
                    res = await session.list_resources()
                    for r in res.resources:
                        r.name = self._ns_name(ns, r.name)
                        if hasattr(r, "uri"):
                            r.uri = f"{ns}__{r.uri}"
                        resources.append(r)
                except Exception:
                    pass  # child may not support resources
            return resources

        @server.list_prompts()
        async def list_prompts():
            prompts: list[Any] = []
            for ns, session in sorted(self._children.items()):
                try:
                    res = await session.list_prompts()
                    for p in res.prompts:
                        p.name = self._ns_name(ns, p.name)
                        prompts.append(p)
                except Exception:
                    pass
            return prompts

        # read_resource and get_prompt are routed dynamically
        @server.read_resource()
        async def read_resource(uri: str):
            for ns, session in self._children.items():
                prefix = f"{ns}__"
                if uri.startswith(prefix):
                    child_uri = uri[len(prefix):]
                    return await session.read_resource(child_uri)
            raise ValueError(f"No child handles resource: {uri}")

        @server.get_prompt()
        async def get_prompt(name: str, arguments: dict[str, str] | None = None):
            for ns, session in self._children.items():
                prefix = f"{ns}__"
                if name.startswith(prefix):
                    child_name = name[len(prefix):]
                    return await session.get_prompt(child_name, arguments)
            raise ValueError(f"No child handles prompt: {name}")

    # ---- cleanup --------------------------------------------------------------

    async def close(self) -> None:
        await self._exit_stack.aclose()

    async def run(self) -> None:
        """Serve via stdio."""
        async with stdio_server() as (read, write):
            await self.server.run(
                read, write, self.server.create_initialization_options()
            )


# ===========================================================================
# Entry point
# ===========================================================================

async def main() -> None:
    gateway = Gateway()
    try:
        await gateway.start()
        await gateway.run()
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
