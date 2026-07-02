#!/usr/bin/env python3
"""MCP stdio server — execute shell commands inside the container.

Exposes one tool: `shell` — runs a command and returns stdout/stderr/exit code.
Gives Claude access to all CLI tools: strings, objdump, angr-solve.py,
fuzz-init.sh, apktool, jadx, bindiff, frida, afl-fuzz, honggfuzz, etc.
"""

import asyncio
import json
import subprocess
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server


server = Server("shell-mcp")


@server.tool()
async def shell(cmd: str, cwd: str = "/workspace", timeout: int = 60) -> str:
    """Run a shell command inside the container.

    Args:
        cmd: Shell command to execute (e.g. 'file /workspace/chall.bin')
        cwd: Working directory (default /workspace)
        timeout: Max execution time in seconds (default 60)

    Returns:
        JSON with stdout, stderr, and returncode.
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return json.dumps({
            "stdout": stdout.decode("utf-8", errors="replace")[:50000],
            "stderr": stderr.decode("utf-8", errors="replace")[:50000],
            "returncode": proc.returncode,
        })
    except asyncio.TimeoutError:
        return json.dumps({"error": f"Command timed out after {timeout}s", "returncode": -1})
    except Exception as e:
        return json.dumps({"error": str(e), "returncode": -1})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
