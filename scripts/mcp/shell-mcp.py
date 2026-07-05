#!/usr/bin/env python3
"""MCP stdio server — execute shell commands inside the container.

Single tool: `shell` — runs any CLI tool (angr, AFL++, honggfuzz, bindiff,
apktool, jadx, gcc, python3, etc.) and returns stdout/stderr/exit code.
"""

import json
import subprocess

from mcp.server import FastMCP
mcp = FastMCP("shell-mcp")


@mcp.tool()
def shell(cmd: str, cwd: str = "/workspace", timeout: int = 60) -> str:
    """Run a shell command inside the container.

    All CLI tools available: angr, afl-fuzz, honggfuzz, bindiff, apktool,
    jadx, gcc, clang, python3, gdb, objdump, strings, radare2, etc.

    Args:
        cmd: Shell command to execute
        cwd: Working directory (default /workspace)
        timeout: Max seconds (default 60, max 300)

    Returns:
        JSON with stdout, stderr, returncode.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=min(timeout, 300),
        )
        return json.dumps({
            "stdout": result.stdout[:50000],
            "stderr": result.stderr[:50000],
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Timed out after {timeout}s", "returncode": -1})
    except Exception as e:
        return json.dumps({"error": str(e), "returncode": -1})


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
