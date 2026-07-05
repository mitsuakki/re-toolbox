# re-toolbox

All-in-one Docker image for reverse engineering — radare2 + Ghidra wired up as
MCP servers, plus BinDiff, angr, AFL++, honggfuzz, and Android tools (apktool,
jadx, frida). Usable with Claude Code, Claude Desktop, Cline, Continue, or any
MCP client.

Headless only — no GUI, no VNC. Everything runs in the terminal or through MCP.

## Requirements

- Docker 23.0+ (BuildKit required — default since 23.0)
- Docker Compose 2.0+ (`docker compose`, not `docker-compose`)

Docker 18.09–22.x users: export `DOCKER_BUILDKIT=1` before building.

## Quick start

```bash
docker compose build
docker compose up -d
docker exec -it toolbox bash
```

Drop binaries in `./workspace` — mounted at `/workspace` inside the container.

To import a binary into Ghidra in one command:

```bash
./scripts/load-ghidra.sh workspace/my-binary          # auto-analyze
./scripts/load-ghidra.sh workspace/my-binary --no-analyze
```

## MCP servers

Three MCP servers are pre-configured. Copy entries from
[`.mcp.json`](.mcp.json) or [`configs/base.json`](configs/base.json) into your
MCP client.

### radare2

Always ready — no server to start. Exposes all r2 analysis capabilities:
disassembly, decompilation (via r2ghidra), hexdump, cross-references, symbols,
search, emulation.

```json
{
  "mcpServers": {
    "radare2": {
      "command": "docker",
      "args": ["exec", "-i", "toolbox", "r2pm", "-r", "r2mcp"]
    }
  }
}
```

### Ghidra headless

Server auto-starts inside the container on port 8089
(`ENABLE_GHIDRA_HEADLESS_MCP=1` in docker-compose.yml). Exposes 200+ tools:
project management, import, auto-analysis, decompilation, cross-references,
dataflow analysis, symbol tables, patching, function tagging, struct/type
management, and debugger support.

```json
{
  "mcpServers": {
    "ghidra-headless": {
      "command": "docker",
      "args": [
        "exec", "-i", "-e", "GHIDRA_MCP_URL=http://127.0.0.1:8089", "toolbox",
        "python3", "/opt/tools/ghidra-mcp/bridge_mcp_ghidra.py"
      ]
    }
  }
}
```

The HTTP API is also reachable directly:

```bash
curl http://localhost:8089/check_connection
curl -X POST "http://localhost:8089/load_program" -d "file=/workspace/mybin"
curl "http://localhost:8089/decompile_function?program=mybin&name=main"
```

### Ghidra GUI (optional)

If you run Ghidra GUI on your host with the GhidraMCP plugin started on port
8080, connect from an MCP client with this entry. The image does not include a
GUI — this bridges to an external Ghidra instance.

```json
{
  "mcpServers": {
    "ghidra-gui": {
      "command": "docker",
      "args": [
        "exec", "-i", "-e", "GHIDRA_MCP_URL=http://host.docker.internal:8080", "toolbox",
        "python3", "/opt/tools/ghidra-mcp/bridge_mcp_ghidra.py"
      ]
    }
  }
}
```

### Shell

Generic shell execution inside the container — gives access to every CLI tool.
Pass any command and get back stdout, stderr, and exit code. Capped at 300
seconds.

```json
{
  "mcpServers": {
    "shell": {
      "command": "docker",
      "args": [
        "exec", "-i", "toolbox",
        "python3", "/opt/tools/scripts/mcp/shell-mcp.py"
      ]
    }
  }
}
```

### angr (built-in MCP)

angr 9.2 ships its own MCP server. Add it as a stdio transport:

```json
{
  "mcpServers": {
    "angr": {
      "command": "docker",
      "args": [
        "exec", "-i", "toolbox",
        "python3", "-m", "angr.mcp"
      ]
    }
  }
}
```

### Where to put the config

| MCP client | File |
|---|---|
| Claude Code | `.claude/mcp.json` (project) or `~/.claude/mcp.json` (global) |
| Claude Desktop | `claude_desktop_config.json` ([docs](https://docs.anthropic.com/en/docs/claude-desktop)) |
| Cline (VS Code) | `cline_mcp_settings.json` |
| Continue | `~/.continue/config.json` |
| Zed | `settings.json` → `{"context_servers": {...}}` |

Restart the client after editing. `docker exec -i toolbox ...` spawns the bridge
on demand — no long-running process to manage on the host.

## CLI tools

### radare2

```bash
r2 -A /workspace/chall              # open + analyze
r2 -c "pdg @ main" /workspace/chall # decompile main via r2ghidra
r2pm -r r2mcp -t                    # list MCP tools exposed by r2mcp
```

### Ghidra headless (analyzeHeadless)

```bash
/opt/tools/ghidra/support/analyzeHeadless /home/ctf/ghidra-projects myproj \
  -import /workspace/chall -overwrite
```

Or use `scripts/load-ghidra.sh` which also loads the binary into the MCP server.

### BinDiff

CLI and MCP. Export `.BinExport` from Ghidra or IDA, then diff:

```bash
bindiff old.BinExport new.BinExport
```

The ghidra-headless MCP exposes `bindiff` and `bindiff_export_from_ghidra` tools
for diffing directly from Ghidra projects.

### angr + Python RE stack

Pre-installed: angr, pwntools, ropper, ropgadget, capstone, unicorn, keystone,
z3, lief, r2pipe, frida-tools, objection.

```bash
python3 -c "
import angr
p = angr.Project('/workspace/chall', auto_load_libs=False)
cfg = p.analyses.CFGFast()
print(f'{len(cfg.kb.functions)} functions, entry at {hex(p.entry)}')
"
```

### Fuzzing

AFL++ and honggfuzz are installed under `/opt/tools/fuzzing/bin` (on PATH).

```bash
# AFL++
mkdir -p fuzz-in && echo AAAA > fuzz-in/seed
afl-fuzz -i fuzz-in -o fuzz-out -- /workspace/chall @@
# black-box / no source: add -Q (QEMU mode)

# honggfuzz
mkdir -p hf-in && echo AAAA > hf-in/seed
honggfuzz -i hf-in -o hf-out -- /workspace/chall ___FILE___
```

### Android RE

```bash
apktool d app.apk -o app_decoded
jadx app.apk -d app_jadx_out
adb devices
frida -U -f com.example.app -l hook.js --no-pause
objection -g com.example.app explore
```

### Other tools

`gdb`, `lldb`, `strace`, `ltrace`, `nasm`, `objdump`, `strings`, `patchelf`,
`gcc`, `clang`, and `python3` are all on PATH.

## Project structure

```
.
├── .mcp.json                  MCP config (copy into your client)
├── configs/base.json          same configs, more documentation
├── docker-compose.yml         one-command start
├── docker/
│   └── Dockerfile             multi-stage build, pinned versions
├── scripts/
│   ├── entrypoint.sh          container entrypoint (starts Ghidra MCP server)
│   ├── load-ghidra.sh         import + load binary into Ghidra MCP
│   └── mcp/
│       └── shell-mcp.py       generic shell MCP server
└── workspace/                 mounted at /workspace — put binaries here
```

## Security

Compose adds `SYS_PTRACE` and disables seccomp (`unconfined`) — required by
gdb, strace, and AFL. Run this container in an isolated VM when analyzing
untrusted binaries.

## Build & release

Builds are validated on every push and PR via GitHub Actions
(`.github/workflows/build.yml`). Pushing a version tag (`v1.0.0`, `v1.0`)
publishes the image to GHCR (`ghcr.io/<user>/re-toolbox`).
