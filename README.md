# re-toolbox

All-in-one Docker container for reverse engineering — radare2 + Ghidra headless
wired up as MCP servers, plus BinDiff, angr, AFL++, honggfuzz, and Android tools
(apktool, jadx, frida). Usable with Claude Code, Claude Desktop, Cline, Continue,
or any MCP client.

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

## MCP

**Single entry point.** Copy the `toolbox` entry from [`.mcp.json`](.mcp.json) into
your MCP client config. The gateway composes all toolbox MCP servers behind one
transport — no need to register each server individually.

```json
{
  "mcpServers": {
    "toolbox": {
      "command": "docker",
      "args": [
        "exec", "-i", "toolbox",
        "python3", "/opt/tools/scripts/mcp/gateway.py"
      ]
    }
  }
}
```

Claude Code users: the project's `.mcp.json` auto-configures this. Other clients:

| MCP client | File |
|---|---|
| Claude Code | `.claude/mcp.json` (project) or `~/.claude/mcp.json` (global) |
| Claude Desktop | `claude_desktop_config.json` ([docs](https://docs.anthropic.com/en/docs/claude-desktop)) |
| Cline (VS Code) | `cline_mcp_settings.json` |
| Continue | `~/.continue/config.json` |
| Zed | `settings.json` → `{"context_servers": {...}}` |

Restart the client after editing. `docker exec -i toolbox ...` spawns the gateway
on demand — no long-running MCP process to manage on the host.

### Architecture

```
MCP client (Claude Code, Desktop, etc.)
  └─ docker exec -i toolbox python3 gateway.py     single stdio transport
       ├─ r2pm -r r2mcp                → r2__* tools
       ├─ bridge_mcp_ghidra.py          → ghidra__* tools (connects to :8089)
       ├─ shell-mcp.py                  → shell__exec tool
       └─ python3 -m angr.mcp           → angr__* tools
```

The gateway starts each child MCP server inside the container and proxies every
request. Tools are **namespaced** (`r2__*`, `ghidra__*`, `shell__*`) so they
never collide. Failed children are logged but don't block the gateway — it runs
in degraded mode with whatever connected.

### Server catalog

| Namespace | Server | What it exposes |
|---|---|---|
| `r2__*` | r2mcp via `r2pm` | Disassembly, decompilation (r2ghidra), hexdump, xrefs, symbols, search, emulation |
| `ghidra__*` | bridge_mcp_ghidra.py → Ghidra headless :8089 | Project mgmt, import, auto-analysis, 200+ tools: decompilation, patching, struct/types, debugger, Bindiff |
| `shell__*` | shell-mcp.py | Arbitrary shell commands — angr, AFL++, honggfuzz, apktool, jadx, gdb, gcc, python3, etc. |
| `angr__*` | angr.mcp (built-in) | Binary analysis — project loading, CFG, symbolic execution, data dependency, VFG |

### Individual servers (advanced)

You can also register servers individually — skip the gateway and connect
directly to a single MCP. Useful for debugging or when you only need one tool.

<details>
<summary>Individual MCP configs (click to expand)</summary>

**radare2** — always ready, no server to start.

```json
{"mcpServers": {"radare2": {"command": "docker", "args": ["exec", "-i", "toolbox", "r2pm", "-r", "r2mcp"]}}}
```

**Ghidra headless** — server auto-starts on :8089 (`ENABLE_GHIDRA_HEADLESS_MCP=1` in docker-compose.yml).

```json
{"mcpServers": {"ghidra-headless": {"command": "docker", "args": ["exec", "-i", "-e", "GHIDRA_MCP_URL=http://127.0.0.1:8089", "toolbox", "python3", "/opt/tools/ghidra-mcp/bridge_mcp_ghidra.py"]}}}
```

**Shell** — arbitrary command execution.

```json
{"mcpServers": {"shell": {"command": "docker", "args": ["exec", "-i", "toolbox", "python3", "/opt/tools/scripts/mcp/shell-mcp.py"]}}}
```

**angr (built-in MCP)** — angr 9.2 ships its own MCP server.

```json
{"mcpServers": {"angr": {"command": "docker", "args": ["exec", "-i", "toolbox", "python3", "-m", "angr.mcp"]}}}
```

</details>

### Ghidra GUI (optional)

If you run Ghidra GUI on your host with the GhidraMCP plugin on port 8080,
connect from an MCP client:

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

### Ghidra tool availability

Ghidra tools come in two categories:

| Category | When available | Examples |
|---|---|---|
| **Static** | Always — no instance needed | `import_file`, `list_instances`, `connect_instance`, `list_tool_groups`, `load_tool_group` |
| **Instance-scoped** | After connecting to a loaded program | `decompile_function`, `list_functions`, `rename_function`, `xrefs_to`, `disassemble_function`, all debugger tools |

Lifecycle:

```
import_file ──→ auto-connect ──→ schema fetch ──→ all 200+ tools available
     │
     └── or: connect_instance ──→ schema fetch ──→ all tools available
```

Use `check_tools` to see what's callable right now:

```
ghidra__check_tools: "decompile_function,list_functions,import_file,bindiff"
→ import_file=callable, decompile_function=not_found (no instance yet)
→ import_file completes → all four = callable
```

Static tools are built into the bridge. Instance-scoped tools are fetched
dynamically from the headless server's `/mcp/schema` after connect. If a tool
shows `not_loaded` (exists but its group isn't loaded), call `load_tool_group`
with the category name. Use `list_tool_groups` to see all categories and their
loaded status.

## Agents

`.claude/agents/` ships with specialized RE agents. Anyone cloning the repo gets
them automatically — Claude Code loads agents from the project's `.claude/`
directory.

| Agent | Model | What it does |
|---|---|---|
| `binary-triage` | haiku | Fast radare2 + shell first-look at unknown binary |
| `ghidra-importer` | sonnet | Import binary into Ghidra headless, run auto-analysis |
| `ghidra-analyst` | sonnet | Static RE — decompile, xrefs, rename, annotate |
| `ghidra-debugger` | sonnet | Dynamic analysis — attach, breakpoints, trace, memory watch |
| `re-orchestrator` | opus | Full pipeline: triage → import → static → dynamic → report |

### Usage examples

```
triage this binary: /workspace/suspicious.elf
import /workspace/challenge.exe into Ghidra
decompile the function at 0x401000 and trace its xrefs
find all strings containing "http" in this binary
trace every call to D2Common.ordinal:10624 with arguments
full reverse engineering analysis on /workspace/malware.bin
```

### Adding your own agents

Add `.md` files to `.claude/agents/`. Frontmatter:

```yaml
---
name: my-agent
description: What it does
model: haiku | sonnet | opus
tools: [Read, Bash, mcp__toolbox__ghidra__*, mcp__toolbox__r2__*, mcp__toolbox__shell__exec]
---
```

`tools` is optional — omit to inherit all tools from the parent session. For MCP
tools, use the namespaced names: `mcp__toolbox__<server>__<tool_name>`.

## CLI tools

### radare2

```bash
r2 -A /workspace/chall              # open + analyze
r2 -c "pdg @ main" /workspace/chall # decompile main via r2ghidra
r2pm -r r2mcp -t                    # list MCP tools exposed by r2mcp
```

### Ghidra headless

**Quick import** via the bundled script:

```bash
/opt/tools/scripts/load-ghidra.sh /workspace/my-binary          # auto-analyze
/opt/tools/scripts/load-ghidra.sh /workspace/my-binary myproj   # named project
/opt/tools/scripts/load-ghidra.sh /workspace/my-binary --no-analyze
```

The script checks MCP server health, imports via `analyzeHeadless`, and calls
`/load_program` to make the binary available to the bridge. Projects land in
`/home/ctf/ghidra-projects` (persisted in the `ghidra-projects` Docker volume).

**Manual import** with analyzeHeadless:

```bash
/opt/tools/ghidra/support/analyzeHeadless /home/ctf/ghidra-projects myproj \
  -import /workspace/chall -overwrite
```

### HTTP API (Ghidra headless)

```bash
curl http://localhost:8089/check_connection
curl -X POST "http://localhost:8089/load_program" -d "file=/workspace/mybin"
curl "http://localhost:8089/decompile_function?program=mybin&name=main"
```

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
├── .mcp.json                    MCP config — paste into your client (single entry)
├── CLAUDE.md                    Agent reference + quickstart for Claude Code
├── docker-compose.yml           One-command start
├── docker/
│   └── Dockerfile               Multi-stage build, pinned versions
├── scripts/
│   ├── entrypoint.sh            Container entrypoint (starts Ghidra MCP daemon)
│   ├── load-ghidra.sh           Import + load binary into Ghidra MCP from CLI
│   └── mcp/
│       ├── gateway.py           MCP gateway — composes all servers behind one transport
│       └── shell-mcp.py         Shell command MCP server
├── .claude/
│   ├── settings.json            Auto-enables project MCP servers
│   └── agents/                  Specialized RE agents (auto-loaded by Claude Code)
│       ├── binary-triage.md     Fast radare2 first-look
│       ├── ghidra-importer.md   Binary import + auto-analysis
│       ├── ghidra-analyst.md    Static RE deep-dive
│       ├── ghidra-debugger.md   Dynamic analysis / debugger
│       └── re-orchestrator.md   Full pipeline coordinator
└── workspace/                   Mounted at /workspace — put binaries here
```

## Security

Compose adds `SYS_PTRACE` and disables seccomp (`unconfined`) — required by
gdb, strace, and AFL. Run this container in an isolated VM when analyzing
untrusted binaries.

## Build & release

Builds are validated on every push and PR via GitHub Actions
(`.github/workflows/build.yml`). Pushing a version tag (`v1.0.0`, `v1.0`)
publishes the image to GHCR (`ghcr.io/<user>/re-toolbox`).
