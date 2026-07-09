#!/usr/bin/env python3
"""
MCP Gateway — HTTP transport (thin wrapper around gateway.py --transport http).

Usage:
  python3 /opt/tools/scripts/mcp/gateway-http.py
  python3 /opt/tools/scripts/mcp/gateway-http.py --port 3100 --host 0.0.0.0

Connect from any MCP client:
  claude mcp add toolbox --transport http http://<host>:3100/mcp
"""

import asyncio
import sys
import os

# Ensure gateway.py is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gateway import Gateway


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MCP Gateway — HTTP transport")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3100)
    args = parser.parse_args()

    gateway = Gateway()
    try:
        await gateway.start()
        await gateway.run_http(host=args.host, port=args.port)
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
