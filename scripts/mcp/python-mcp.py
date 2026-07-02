#!/usr/bin/env python3

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


@mcp.tool()
def python(code: str, timeout: int = 120) -> str:
    """Execute Python code with RE libraries pre-loaded (angr, pwntools, z3, lief, capstone).

    Args:
        code: Python code to execute. Libraries already imported — just use them.
        timeout: Max execution time in seconds (default 120)

    Returns:
        Captured stdout or error traceback.
    """
    import signal

    namespace = {}
    full_code = PRELUDE + "\n" + code
    buf = io.StringIO()

    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        exec(full_code, namespace)
        output = buf.getvalue()
        return json.dumps({
            "stdout": output[:50000] if output else "(no output)",
            "returncode": 0,
        })
    except Exception:
        tb = traceback.format_exc()
        return json.dumps({"error": tb[:50000], "returncode": 1})
    finally:
        sys.stdout = old_stdout


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
