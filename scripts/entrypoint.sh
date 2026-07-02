#!/usr/bin/env bash

set -euo pipefail

GHIDRA_MCP_PORT="${GHIDRA_MCP_PORT:-8089}"
GHIDRA_GUI_PORT="${GHIDRA_GUI_PORT:-8080}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PORT="${VNC_PORT:-5900}"

log() { echo "[entrypoint] $*" >&2; }

# --- Optional: Ghidra headless MCP server -----------------------------------
if [[ "${ENABLE_GHIDRA_HEADLESS_MCP:-1}" == "1" ]]; then
  if [[ -f /opt/tools/ghidra-mcp/docker/GhidraMCPHeadless.jar ]]; then
    log "Starting Ghidra headless MCP server on :${GHIDRA_MCP_PORT}"
    nohup java -jar /opt/tools/ghidra-mcp/docker/GhidraMCPHeadless.jar \
      --bind 127.0.0.1 --port "${GHIDRA_MCP_PORT}" \
      > /tmp/ghidra-mcp-headless.log 2>&1 &
  else
    log "ghidra-mcp headless jar not found (build step may have been skipped at image build time)."
    log "Build manually inside the container: cd /opt/tools/ghidra-mcp && mvn -DskipTests package"
  fi
fi

# --- Optional: GUI Ghidra over VNC + noVNC (browser access) -----------------
if [[ "${ENABLE_GHIDRA_GUI:-0}" == "1" ]]; then
  log "Starting Xvfb + fluxbox + x11vnc + noVNC on :${NOVNC_PORT}"
  Xvfb :1 -screen 0 1600x900x24 &
  export DISPLAY=:1
  fluxbox &
  x11vnc -display :1 -forever -shared -nopw -rfbport "${VNC_PORT}" &
  websockify --web /usr/share/novnc/ "${NOVNC_PORT}" "localhost:${VNC_PORT}" &
  log "Open the noVNC client at http://localhost:${NOVNC_PORT}/vnc.html then launch: ghidraRun"
fi

log "radare2 + r2mcp ready (invoke MCP via: r2pm -r r2mcp, see /opt/tools/configs)"
log "angr / pwntools / AFL++ / honggfuzz / BinDiff / apktool / jadx / frida available on PATH"

exec "$@"
