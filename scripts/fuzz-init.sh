#!/usr/bin/env bash

set -euo pipefail

MODE="${1:?usage: fuzz-init.sh <afl|hfuzz> <target_binary> [args...]}"
shift
TARGET="${1:?missing target binary path}"
shift || true

WORKDIR="$(pwd)/fuzz-$(basename "$TARGET")-$MODE"
mkdir -p "$WORKDIR/in" "$WORKDIR/out"

# Minimal non-empty seed if none provided
if [[ -z "$(ls -A "$WORKDIR/in")" ]]; then
  printf 'AAAAAAAA' > "$WORKDIR/in/seed1"
fi

case "$MODE" in
  afl)
    cat <<EOF
[fuzz-init] AFL++ scaffold ready at: $WORKDIR

Recompile with instrumentation if you have source:
  CC=afl-clang-fast CXX=afl-clang-fast++ make

Run the fuzzer (binary mode / no source -> QEMU/AFL_USE_FORK or afl-qemu):
  afl-fuzz -i $WORKDIR/in -o $WORKDIR/out -- $TARGET $* @@

For closed-source binaries without recompilation, add -Q (QEMU mode):
  afl-fuzz -Q -i $WORKDIR/in -o $WORKDIR/out -- $TARGET $* @@

Triage crashes afterwards with:
  afl-tmin -i <crash_file> -o <minimized> -- $TARGET $* @@
EOF
    ;;
  hfuzz)
    cat <<EOF
[fuzz-init] honggfuzz scaffold ready at: $WORKDIR

Recompile with instrumentation if you have source:
  CC=hfuzz-clang CXX=hfuzz-clang++ make

Run the fuzzer:
  honggfuzz -i $WORKDIR/in -o $WORKDIR/out -- $TARGET $* ___FILE___

(___FILE___ is honggfuzz's placeholder for the mutated input file path)
EOF
    ;;
  *)
    echo "Unknown mode: $MODE (expected afl|hfuzz)" >&2
    exit 1
    ;;
esac
