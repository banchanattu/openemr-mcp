"""
Smoke test for the OpenEMR MCP Streamable HTTP server.

Usage:
    uv run python examples/smoke_test_http.py
    uv run python examples/smoke_test_http.py --url http://127.0.0.1:8080/mcp
"""

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the OpenEMR MCP HTTP endpoint.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8305/mcp",
        help="Streamable HTTP MCP endpoint URL.",
    )
    parser.add_argument(
        "--query",
        default="John",
        help="Patient search query to use for the smoke test.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    async with streamable_http_client(args.url) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            print("Available tools:", ", ".join(tool_names))

            result = await session.call_tool(
                "openemr_patient_search",
                arguments={"query": args.query},
            )

            print("Tool result:")
            if result.structuredContent is not None:
                print(json.dumps(result.structuredContent, indent=2, default=str))
                return

            for item in result.content:
                text = getattr(item, "text", None)
                if text is not None:
                    print(text)


if __name__ == "__main__":
    asyncio.run(_main())
