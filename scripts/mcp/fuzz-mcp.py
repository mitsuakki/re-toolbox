#!/usr/bin/env python3
"""MCP stdio server — fuzzing harness setup (AFL++ / honggfuzz).

Wraps fuzz-init.sh with structured MCP tools.
"""

import asyncio
import json
import subprocess
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server


server = Server("fuzz-mcp")
FUZZ_INIT = "/opt/tools/scripts/fuzz-init.sh"


@server.tool()
async def fuzz_init(
    mode: str,
    target: str,
    args: str = "",
    cwd: str = "/workspace",
) -> str:
    """Scaffold a fuzzing session for a binary.

    Creates in/ and out/ directories, writes a minimal seed file, and
    prints the commands to compile (if you have source) and run the fuzzer.

    Args:
        mode: "afl" for AFL++ or "hfuzz" for honggfuzz
        target: Path to the target binary
        args: Optional extra arguments passed through to the fuzzer command
        cwd: Working directory (default /workspace)
    """
    if mode not in ("afl", "hfuzz"):
        return json.dumps({"error": f"Unknown mode '{mode}'. Use 'afl' or 'hfuzz'.", "returncode": 1})

    try:
        proc = await asyncio.create_subprocess_exec(
            FUZZ_INIT, mode, target, *args.split() if args else [],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=30
        )
        return json.dumps({
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": proc.returncode,
        })
    except asyncio.TimeoutError:
        return json.dumps({"error": "Command timed out after 30s", "returncode": -1})
    except Exception as e:
        return json.dumps({"error": str(e), "returncode": -1})


@server.tool()
async def fuzz_run(
    mode: str,
    target: str,
    args: str = "",
    cwd: str = "/workspace",
    timeout: int = 30,
) -> str:
    """Run the fuzzer directly (short duration — use for quick smoke tests).

    Args:
        mode: "afl" or "hfuzz"
        target: Path to the target binary
        args: Extra arguments for the fuzzer
        cwd: Working directory
        timeout: Max run time in seconds (default 30)
    """
    workdir = f"{cwd}/fuzz-{target.split('/')[-1]}-{mode}"

    if mode == "afl":
        cmd = f"timeout {timeout} afl-fuzz -i {workdir}/in -o {workdir}/out -- {target} {args}"
    else:
        cmd = f"timeout {timeout} honggfuzz -i {workdir}/in -o {workdir}/out -- {target} {args} ___FILE___"

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(), timeout=timeout + 5
    )
    return json.dumps({
        "stdout": stdout.decode("utf-8", errors="replace")[-10000:],
        "stderr": stderr.decode("utf-8", errors="replace")[-10000:],
        "returncode": proc.returncode,
    })


@server.tool()
async def fuzz_triage(mode: str, target: str, crash_file: str, cwd: str = "/workspace") -> str:
    """Minimize a crash file found by the fuzzer (AFL only).

    Args:
        mode: "afl" (honggfuzz triage not yet supported)
        target: Path to the target binary
        crash_file: Path to the crash file to minimize
        cwd: Working directory
    """
    if mode != "afl":
        return json.dumps({"error": "Triage only supported for AFL++ mode", "returncode": 1})

    minimized = f"{crash_file}.min"
    proc = await asyncio.create_subprocess_shell(
        f"afl-tmin -i {crash_file} -o {minimized} -- {target}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    return json.dumps({
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "minimized": minimized if proc.returncode == 0 else None,
        "returncode": proc.returncode,
    })


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
