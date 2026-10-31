
from contextlib import asynccontextmanager

import httpx2

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .auth import create_wispr_oauth


WISPR_MCP_URL = "https://api.wisprflow.ai/connect/mcp"


@asynccontextmanager
async def wispr_session():
    """Open an authenticated Wispr MCP session using the existing OAuth flow."""
    oauth_provider, callback = create_wispr_oauth()
    try:
        async with httpx2.AsyncClient(
            auth=oauth_provider,
            timeout=httpx2.Timeout(30.0, read=300.0),
        ) as http_client:
            async with streamable_http_client(
                url=WISPR_MCP_URL, http_client=http_client
            ) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session
    finally:
        callback.stop()


async def discover_wispr_tools():
    oauth_provider, callback = create_wispr_oauth()

    try:
        async with httpx2.AsyncClient(
            auth=oauth_provider,
            timeout=httpx2.Timeout(30.0, read=300.0),
        ) as http_client:

            async with streamable_http_client(
                url=WISPR_MCP_URL,
                http_client=http_client,
            ) as (read_stream, write_stream):

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    print("Initializing Wispr MCP session...")

                    await session.initialize()

                    print("Connected to Wispr Flow.")

                    result = await session.list_tools()

                    tools = []

                    for tool in result.tools:
                        tool_data = {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.input_schema,
                        }

                        tools.append(tool_data)

                    return tools

    finally:
        callback.stop()
