#!/bin/bash
set -euo pipefail

# ============================================================================
# toolbox entrypoint — start background services, then hand off to CMD
# ============================================================================

# -- Ghidra headless MCP HTTP server -----------------------------------------
if [[ "${ENABLE_GHIDRA_HEADLESS_MCP:-0}" == "1" ]]; then
    GHIDRA_MCP_DIR="/opt/tools/ghidra-mcp"
    GHIDRA_JAR="${GHIDRA_MCP_DIR}/docker/GhidraMCPHeadless.jar"
    GHIDRA_MCP_PORT="${GHIDRA_MCP_PORT:-8089}"
    GHIDRA_MCP_HOST="${GHIDRA_MCP_HOST:-0.0.0.0}"
    GHIDRA_MCP_TOKEN="${GHIDRA_MCP_AUTH_TOKEN:-re-toolbox-dev-secret}"

    if [[ -f "${GHIDRA_JAR}" ]]; then
        echo "[entrypoint] Starting ghidra-mcp headless on ${GHIDRA_MCP_HOST}:${GHIDRA_MCP_PORT}…"

        # Build classpath: ghidra-mcp JAR + Ghidra's Framework/Features/Processors libs
        GHIDRA_HOME="${GHIDRA_INSTALL_DIR:-/opt/tools/ghidra}"
        CLASSPATH="${GHIDRA_JAR}"
        for jar in "${GHIDRA_HOME}"/Ghidra/Framework/*/lib/*.jar; do
            [ -f "$jar" ] && CLASSPATH="${CLASSPATH}:${jar}"
        done
        for jar in "${GHIDRA_HOME}"/Ghidra/Features/*/lib/*.jar; do
            [ -f "$jar" ] && CLASSPATH="${CLASSPATH}:${jar}"
        done
        for jar in "${GHIDRA_HOME}"/Ghidra/Processors/*/lib/*.jar; do
            [ -f "$jar" ] && CLASSPATH="${CLASSPATH}:${jar}"
        done

        export GHIDRA_MCP_AUTH_TOKEN="${GHIDRA_MCP_TOKEN}"

        java -Xmx4g -XX:+UseG1GC \
            -Dghidra.home="${GHIDRA_HOME}" \
            -Dapplication.name=GhidraMCP \
            -classpath "${CLASSPATH}" \
            com.xebyte.headless.GhidraMCPHeadlessServer \
            --bind "${GHIDRA_MCP_HOST}" \
            --port "${GHIDRA_MCP_PORT}" \
            &>/tmp/ghidra-mcp.log &
        GHIDRA_PID=$!

        # Wait until the HTTP server is accepting connections
        echo "[entrypoint] Waiting for ghidra-mcp to be ready…"
        for i in $(seq 1 30); do
            if curl -sf -o /dev/null -H "Authorization: Bearer ${GHIDRA_MCP_TOKEN}" \
                    "http://127.0.0.1:${GHIDRA_MCP_PORT}/health" 2>/dev/null; then
                echo "[entrypoint] ghidra-mcp ready (pid ${GHIDRA_PID})"
                break
            fi
            sleep 1
        done

        if ! kill -0 "${GHIDRA_PID}" 2>/dev/null; then
            echo "[entrypoint] WARNING: ghidra-mcp failed to start. Check /tmp/ghidra-mcp.log"
        fi
    else
        echo "[entrypoint] WARNING: GhidraMCPHeadless.jar not found at ${GHIDRA_JAR} — skipping"
    fi
fi

# -- MCP Gateway (StreamableHTTP) --------------------------------------------
if [[ "${ENABLE_GATEWAY_HTTP:-0}" == "1" ]]; then
    GATEWAY_PORT="${GATEWAY_HTTP_PORT:-3100}"
    GATEWAY_HOST="${GATEWAY_HTTP_HOST:-0.0.0.0}"
    echo "[entrypoint] Starting MCP gateway HTTP on ${GATEWAY_HOST}:${GATEWAY_PORT}…"
    python3 /opt/tools/scripts/mcp/gateway.py \
        --transport http \
        --host "${GATEWAY_HOST}" \
        --port "${GATEWAY_PORT}" \
        &>/tmp/gateway-http.log &
    GATEWAY_PID=$!

    echo "[entrypoint] Waiting for MCP gateway to be ready…"
    for i in $(seq 1 15); do
        if curl -sf -o /dev/null "http://127.0.0.1:${GATEWAY_PORT}/mcp" 2>/dev/null; then
            echo "[entrypoint] MCP gateway ready (pid ${GATEWAY_PID})"
            break
        fi
        sleep 1
    done
fi

# -- Hand off ----------------------------------------------------------------
echo "[entrypoint] toolbox ready. Executing: $*"
exec "$@"
