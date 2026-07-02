#!/usr/bin/env python3

import argparse
import sys

import angr
import claripy


def cmd_info(args):
    proj = angr.Project(args.binary, auto_load_libs=False)
    cfg = proj.analyses.CFGFast()
    print(f"Arch: {proj.arch.name}  Entry: {hex(proj.entry)}")
    print(f"Functions found: {len(cfg.kb.functions)}")
    for addr, func in list(cfg.kb.functions.items())[:50]:
        print(f"  {hex(addr):>12}  {func.name}")


def cmd_find(args):
    proj = angr.Project(args.binary, auto_load_libs=False)

    if args.stdin_len:
        sym_stdin = claripy.BVS("stdin", 8 * args.stdin_len)
        state = proj.factory.full_init_state(
            stdin=angr.SimFileStream(name="stdin", content=sym_stdin, has_end=False)
        )
        for byte in sym_stdin.chop(8):
            state.solver.add(byte >= 0x20, byte <= 0x7E)  # printable ASCII
    else:
        state = proj.factory.entry_state()

    simgr = proj.factory.simgr(state)

    find = int(args.find_addr, 16) if args.find_addr else (lambda s: args.find.encode() in s.posix.dumps(1))
    avoid = int(args.avoid_addr, 16) if args.avoid_addr else (
        (lambda s: args.avoid.encode() in s.posix.dumps(1)) if args.avoid else None
    )

    kwargs = {"find": find}
    if avoid is not None:
        kwargs["avoid"] = avoid

    simgr.explore(**kwargs)

    if simgr.found:
        found = simgr.found[0]
        if args.stdin_len:
            print("[+] Solution stdin:", found.solver.eval(sym_stdin, cast_to=bytes))
        print("[+] Output:", found.posix.dumps(1))
    else:
        print("[-] No path found matching the success condition.", file=sys.stderr)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="CFG/function overview")
    p_info.add_argument("binary")
    p_info.set_defaults(func=cmd_info)

    p_find = sub.add_parser("find", help="symbolic search for a success state")
    p_find.add_argument("binary")
    p_find.add_argument("--stdin-len", type=int, default=0, help="bytes of symbolic stdin to allocate")
    p_find.add_argument("--find", help="substring expected in stdout on success")
    p_find.add_argument("--avoid", help="substring indicating failure")
    p_find.add_argument("--find-addr", help="hex address considered success")
    p_find.add_argument("--avoid-addr", help="hex address considered failure")
    p_find.set_defaults(func=cmd_find)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
