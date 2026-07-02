# re-toolbox

All-in-one Docker image for reverse engineering — radare2 + Ghidra wired up as
MCP servers (usable by Claude Desktop or any MCP client), plus BinDiff, angr,
AFL++, honggfuzz, and Android tools (apktool, jadx, frida).

**Headless only** — no GUI, no VNC. Everything runs in the terminal or through
MCP.

## Quick start

```bash
docker compose build
docker compose up -d
docker exec -it toolbox bash
```

Drop challenge binaries in `./workspace` — mounted at `/workspace` inside the
container.

## Connect MCP tools to your LLM

The image exposes MCP servers. Copy entries from
[`configs/base.json`](configs/base.json) into your MCP client config file.

### Claude Desktop

Edit `claude_desktop_config.json` ([where to find it](https://docs.anthropic.com/en/docs/claude-desktop)):

**radare2** — always ready, no server to start:

```json
{
  "mcpServers": {
    "radare2": {
      "command": "docker",
      "args": ["exec", "-i", "ctf-re", "r2pm", "-r", "r2mcp"]
    }
  }
}
```

**Ghidra headless** — server auto-starts inside the container on port 8089
(`ENABLE_GHIDRA_HEADLESS_MCP=1` by default, exposed in `docker-compose.yml`):

```json
{
  "mcpServers": {
    "ghidra-headless": {
      "command": "docker",
      "args": [
        "exec", "-i", "ctf-re",
        "python3", "/opt/tools/ghidra-mcp/bridge_mcp_ghidra.py",
        "--ghidra-server", "http://127.0.0.1:8089/"
      ]
    }
  }
}
```

**Ghidra GUI** (optional) — if you run Ghidra GUI on your host with the
GhidraMCP plugin started on port 8080, use this entry to connect from an MCP
client. The image does **not** include a GUI — this is for an external Ghidra
instance:

```json
{
  "mcpServers": {
    "ghidra-gui": {
      "command": "docker",
      "args": [
        "exec", "-i", "ctf-re",
        "python3", "/opt/tools/ghidra-mcp/bridge_mcp_ghidra.py",
        "--ghidra-server", "http://host.docker.internal:8080/"
      ]
    }
  }
}
```

Restart your MCP client after editing the config.

### Claude Code (CLI)

Same format, different file. Create `.claude/mcp.json` in your project root
(already done in this repo) or `~/.claude/mcp.json` for all projects:

```json
{
  "mcpServers": {
    "radare2": {
      "command": "docker",
      "args": ["exec", "-i", "ctf-re", "r2pm", "-r", "r2mcp"]
    },
    "ghidra-headless": {
      "command": "docker",
      "args": [
        "exec", "-i", "ctf-re",
        "python3", "/opt/tools/ghidra-mcp/bridge_mcp_ghidra.py",
        "--ghidra-server", "http://127.0.0.1:8089/"
      ]
    }
  }
}
```

Restart Claude Code after editing. MCP tools appear automatically.

### Other MCP clients (Cline, Continue, Zed, etc.)

Same `command` + `args` blocks work with any stdio MCP client.
`docker exec -i ctf-re ...` spawns the bridge on demand — no long-running
process to manage on the host.

## Tools

### radare2 + r2mcp

Pre-installed. `r2ghidra` is also installed — `pdg` decompiles via Ghidra's
SLEIGH engine directly in r2, no Ghidra needed.

```bash
r2 -A /workspace/chall          # open + analyze
r2pm -r r2mcp -t                # list MCP tools exposed
```

### Ghidra headless

Server auto-starts on port 8089. Exposes 200+ tools: project management, import,
auto-analysis, decompilation, symbols, cross-references, patching.

```bash
curl http://localhost:8089/check_connection
curl -X POST -d "file=/workspace/mybin" http://localhost:8089/load_program
curl -X POST "http://localhost:8089/run_analysis?program=mybin"
curl "http://localhost:8089/decompile_function?program=mybin&name=main"
```

### BinDiff

CLI only. Export `.BinExport` from Ghidra or IDA, then:

```bash
bindiff old.BinExport new.BinExport
```

### angr + Python RE stack

Pre-installed: angr, pwntools, ropper, capstone, unicorn, keystone, z3, lief,
r2pipe.

```bash
angr-solve.py info ./chall
angr-solve.py find ./chall --stdin-len 32 --find "Correct" --avoid "Wrong"
angr-solve.py find ./chall --find-addr 0x401300 --avoid-addr 0x401234
```

### Fuzzing (AFL++ / honggfuzz)

```bash
fuzz-init.sh afl ./chall
afl-fuzz -i fuzz-chall-afl/in -o fuzz-chall-afl/out -- ./chall @@

fuzz-init.sh hfuzz ./chall
honggfuzz -i fuzz-chall-hfuzz/in -o fuzz-chall-hfuzz/out -- ./chall ___FILE___
```

Closed-source binaries without recompilation: `afl-fuzz -Q ...` (QEMU mode).

### Android RE

```bash
apktool d app.apk -o app_decoded
jadx app.apk -d app_jadx_out
adb devices
frida -U -f com.example.app -l hook.js --no-pause
objection -g com.example.app explore
```

## Security

Compose adds `SYS_PTRACE` and disables seccomp (`unconfined`) — required by
gdb, strace, and AFL. Run this container in an isolated VM when analyzing
untrusted binaries.
