#!/usr/bin/env python3

import json
import subprocess

from mcp.server import FastMCP
mcp = FastMCP("fuzz-mcp")

FUZZ_INIT = "/opt/tools/scripts/fuzz-init.sh"

@mcp.tool()
def fuzz_init(
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
        cmd = [FUZZ_INIT, mode, target]
        if args:
            cmd.extend(args.split())
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        return json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Command timed out after 30s", "returncode": -1})
    except Exception as e:
        return json.dumps({"error": str(e), "returncode": -1})


@mcp.tool()
def fuzz_run(
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
    try:
        workdir = f"{cwd}/fuzz-{target.split('/')[-1]}-{mode}"

        if mode == "afl":
            cmd = f"timeout {timeout} afl-fuzz -i {workdir}/in -o {workdir}/out -- {target} {args}"
        elif mode == "hfuzz":
            cmd = f"timeout {timeout} honggfuzz -i {workdir}/in -o {workdir}/out -- {target} {args} ___FILE___"
        else:
            return json.dumps({"error": f"Unknown mode '{mode}'. Use 'afl' or 'hfuzz'.", "returncode": 1})

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout + 5,
        )
        return json.dumps({
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-10000:],
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Command timed out after {timeout}s", "returncode": -1})
    except Exception as e:
        return json.dumps({"error": str(e), "returncode": -1})


@mcp.tool()
def fuzz_triage(mode: str, target: str, crash_file: str, cwd: str = "/workspace") -> str:
    """Minimize a crash file found by the fuzzer (AFL only).

    Args:
        mode: "afl" (honggfuzz triage not yet supported)
        target: Path to the target binary
        crash_file: Path to the crash file to minimize
        cwd: Working directory
    """
    if mode != "afl":
        return json.dumps({"error": "Triage only supported for AFL++ mode", "returncode": 1})

    try:
        minimized = f"{crash_file}.min"
        result = subprocess.run(
            f"afl-tmin -i {crash_file} -o {minimized} -- {target}",
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60,
        )
        return json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "minimized": minimized if result.returncode == 0 else None,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Triage timed out after 60s", "returncode": -1})
    except Exception as e:
        return json.dumps({"error": str(e), "returncode": -1})


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
