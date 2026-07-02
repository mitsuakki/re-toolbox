#!/usr/bin/env python3
"""MCP stdio server — execute shell commands inside the container.

Exposes one tool: `shell` — runs a command and returns stdout/stderr/exit code.
Gives Claude access to all CLI tools: strings, objdump, angr-solve.py,
fuzz-init.sh, apktool, jadx, bindiff, frida, afl-fuzz, honggfuzz, etc.
"""

import json
import subprocess

from mcp.server import FastMCP
mcp = FastMCP("shell-mcp")

@mcp.tool()
def shell(cmd: str, cwd: str = "/workspace", timeout: int = 60) -> str:
    """Run a shell command inside the container.

    Args:
        cmd: Shell command to execute (e.g. 'file /workspace/chall.bin')
        cwd: Working directory (default /workspace)
        timeout: Max execution time in seconds (default 60)

    Returns:
        JSON with stdout, stderr, and returncode.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return json.dumps({
            "stdout": result.stdout[:50000],
            "stderr": result.stderr[:50000],
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Command timed out after {timeout}s", "returncode": -1})
    except Exception as e:
        return json.dumps({"error": str(e), "returncode": -1})


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
