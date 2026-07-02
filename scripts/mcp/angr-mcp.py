#!/usr/bin/env python3
"""MCP stdio server — symbolic/concolic analysis via angr.

Exposes angr-solve.py capabilities as structured MCP tools:
- binary_info: CFG + function overview
- symbolic_find: find a path to a success state
"""

import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server


server = Server("angr-mcp")


@server.tool()
async def binary_info(binary: str) -> str:
    """Analyze a binary with angr — architecture, entry point, function list.

    Args:
        binary: Path to the binary file (e.g. /workspace/chall.bin)
    """
    import angr
    proj = angr.Project(binary, auto_load_libs=False)
    cfg = proj.analyses.CFGFast()
    funcs = []
    for addr, func in list(cfg.kb.functions.items())[:100]:
        funcs.append({"addr": hex(addr), "name": func.name})
    return json.dumps({
        "arch": proj.arch.name,
        "entry": hex(proj.entry),
        "function_count": len(cfg.kb.functions),
        "functions": funcs,
    })


@server.tool()
async def symbolic_find(
    binary: str,
    find: str = "",
    avoid: str = "",
    find_addr: str = "",
    avoid_addr: str = "",
    stdin_len: int = 0,
) -> str:
    """Symbolic exploration — find a path to a success state.

    Args:
        binary: Path to the binary file
        find: Substring expected in stdout on success
        avoid: Substring in stdout indicating failure (optional)
        find_addr: Hex address considered success (optional, use instead of find)
        avoid_addr: Hex address considered failure (optional)
        stdin_len: Bytes of symbolic stdin to allocate (0 = concrete entry state)
    """
    import angr
    import claripy

    proj = angr.Project(binary, auto_load_libs=False)

    if stdin_len:
        sym_stdin = claripy.BVS("stdin", 8 * stdin_len)
        state = proj.factory.full_init_state(
            stdin=angr.SimFileStream(name="stdin", content=sym_stdin, has_end=False)
        )
        for byte in sym_stdin.chop(8):
            state.solver.add(byte >= 0x20, byte <= 0x7E)
    else:
        state = proj.factory.entry_state()

    simgr = proj.factory.simgr(state)

    find_target = int(find_addr, 16) if find_addr else (
        (lambda s: find.encode() in s.posix.dumps(1)) if find else None
    )
    avoid_target = int(avoid_addr, 16) if avoid_addr else (
        (lambda s: avoid.encode() in s.posix.dumps(1)) if avoid else None
    )

    if find_target is None:
        return json.dumps({"error": "Must specify --find or --find-addr", "returncode": 1})

    kwargs = {"find": find_target}
    if avoid_target is not None:
        kwargs["avoid"] = avoid_target

    simgr.explore(**kwargs)

    if simgr.found:
        found = simgr.found[0]
        result = {
            "found": True,
            "stdout": found.posix.dumps(1).decode("utf-8", errors="replace")[:10000],
        }
        if stdin_len:
            solution = found.solver.eval(sym_stdin, cast_to=bytes)
            # filter to printable
            result["stdin"] = "".join(
                chr(b) if 0x20 <= b <= 0x7E else f"\\x{b:02x}"
                for b in solution
            )
        return json.dumps(result)
    else:
        return json.dumps({
            "found": False,
            "active_states": len(simgr.active),
            "deadended": len(simgr.deadended),
            "errored": len(simgr.errored),
        })


@server.tool()
async def list_functions(binary: str, limit: int = 200) -> str:
    """List all functions found by angr's CFG analysis.

    Args:
        binary: Path to the binary file
        limit: Max functions to return (default 200)
    """
    import angr
    proj = angr.Project(binary, auto_load_libs=False)
    cfg = proj.analyses.CFGFast()
    funcs = []
    for addr, func in list(cfg.kb.functions.items())[:limit]:
        funcs.append({"addr": hex(addr), "name": func.name, "size": func.size})
    return json.dumps({
        "total": len(cfg.kb.functions),
        "returned": len(funcs),
        "functions": funcs,
    })


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
