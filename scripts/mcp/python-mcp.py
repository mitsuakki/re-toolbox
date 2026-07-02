#!/usr/bin/env python3
"""MCP stdio server — execute Python code with all RE libraries pre-imported.

Exposes one tool: `python` — runs Python code with angr, pwntools, claripy,
z3, lief, capstone, unicorn, etc. already available.
"""

import asyncio
import json
import sys
import io
import traceback

from mcp.server import Server
from mcp.server.stdio import stdio_server


server = Server("python-mcp")

PRELUDE = """
import angr, claripy, pwntools
import z3, lief, capstone
from pwn import *
"""


@server.tool()
async def python(code: str, timeout: int = 120) -> str:
    """Execute Python code with RE libraries pre-loaded (angr, pwntools, z3, lief, capstone).

    Args:
        code: Python code to execute. Libraries already imported — just use them.
        timeout: Max execution time in seconds (default 120)

    Returns:
        Captured stdout or error traceback.
    """
    namespace = {}
    full_code = PRELUDE + "\n" + code
    buf = io.StringIO()

    async def run():
        exec(full_code, namespace)

    try:
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            await asyncio.wait_for(asyncio.to_thread(lambda: exec(full_code, namespace)), timeout=timeout)
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        return json.dumps({
            "stdout": output[:50000] if output else "(no output)",
            "returncode": 0,
        })
    except asyncio.TimeoutError:
        sys.stdout = old_stdout
        return json.dumps({"error": f"Code timed out after {timeout}s", "returncode": -1})
    except Exception:
        sys.stdout = old_stdout
        tb = traceback.format_exc()
        return json.dumps({"error": tb[:50000], "returncode": 1})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
