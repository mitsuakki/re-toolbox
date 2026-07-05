#!/usr/bin/env bash

set -euo pipefail

GHIDRA_MCP_PORT="${GHIDRA_MCP_PORT:-8089}"

log() { echo "[entrypoint] $*" >&2; }

# --- Ghidra headless MCP server ---------------------------------------------
if [[ "${ENABLE_GHIDRA_HEADLESS_MCP:-1}" == "1" ]]; then
  if [[ -f /opt/tools/ghidra-mcp/docker/GhidraMCPHeadless.jar ]]; then
    log "Starting Ghidra headless MCP server on 127.0.0.1:${GHIDRA_MCP_PORT}"

    # Build classpath: jar + all Ghidra runtime jars
    GHIDRA_HOME="${GHIDRA_INSTALL_DIR:-/opt/tools/ghidra}"
    CP="/opt/tools/ghidra-mcp/docker/GhidraMCPHeadless.jar"
    for d in Framework Features Processors Debug; do
      for j in "${GHIDRA_HOME}/Ghidra/${d}"/*/lib/*.jar; do
        [ -f "$j" ] && CP="${CP}:${j}"
      done
    done

    nohup java -Xmx4g -XX:+UseG1GC \
      -Dghidra.home="${GHIDRA_HOME}" \
      -classpath "${CP}" \
      com.xebyte.headless.GhidraMCPHeadlessServer \
      --bind 127.0.0.1 --port "${GHIDRA_MCP_PORT}" \
      > /tmp/ghidra-mcp-headless.log 2>&1 &
  else
    log "ghidra-mcp headless jar not found (build step may have been skipped or failed at image build time)."
    log "Build manually inside the container with:"
    log "  cd /opt/tools/ghidra-mcp"
    log "  python3 -m tools.setup ensure-prereqs --ghidra-path \"\${GHIDRA_INSTALL_DIR}\""
    log "  mvn -DskipTests -Pheadless clean package"
    log "  cp target/*Headless*.jar docker/GhidraMCPHeadless.jar"
    log "Note: ghidra-mcp's pom.xml pins a specific Ghidra <ghidra.version>;"
    log "if that no longer matches the Ghidra release baked into this image"
    log "(currently under \${GHIDRA_INSTALL_DIR}), ensure-prereqs will fail fast"
    log "with a version-mismatch error -- update GHIDRA_VERSION in the Dockerfile"
    log "to match and rebuild the image."
  fi
fi

log "radare2 + r2mcp ready (invoke MCP via: r2pm -r r2mcp, see /opt/tools/configs)"
log "angr / pwntools / AFL++ / honggfuzz / BinDiff / apktool / jadx / frida available on PATH"

exec "$@"