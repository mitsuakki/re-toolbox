#!/usr/bin/env python3

import asyncio
import json
import sys
import io
import traceback

from mcp.server import FastMCP
mcp = FastMCP("python-mcp")

PRELUDE = """
import os
# pwntools tries curses.setupterm() which fails on piped stdio (no TTY in MCP).
# Suppress terminal detection before importing pwn.
os.environ.setdefault("PWNLIB_NOTERM", "1")
import angr, claripy
import z3, lief, capstone
from pwn import *
"""


def _exec_sync(full_code: str, namespace: dict, buf: io.StringIO) -> str:
    """Run exec in a worker thread. Must be sync — asyncio.to_thread needs it."""
    sys.stdout = buf
    try:
        exec(full_code, namespace)
    finally:
        sys.stdout = sys.__stdout__


@mcp.tool()
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

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_exec_sync, full_code, namespace, buf),
            timeout=timeout,
        )
        output = buf.getvalue()
        return json.dumps({
            "stdout": output[:50000] if output else "(no output)",
            "returncode": 0,
        })
    except asyncio.TimeoutError:
        return json.dumps({
            "error": f"Execution timed out after {timeout}s",
            "returncode": 1,
        })
    except Exception:
        tb = traceback.format_exc()
        return json.dumps({"error": tb[:50000], "returncode": 1})


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
