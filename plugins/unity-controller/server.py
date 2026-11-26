"""Connect Cage's stdio client to a configured Unity MCP Streamable HTTP service."""
import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server import create_proxy


def http_client(**options):
    # Keep credentials on the configured endpoint; don't inherit a host proxy.
    options["follow_redirects"] = False
    return httpx.AsyncClient(trust_env=False, **options)


def make_client():
    url = os.environ.get("UNITY_CONTROLLER_URL", "http://127.0.0.1:8083/mcp").strip()
    endpoint = urlsplit(url)
    if endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.fragment:
        raise ValueError("Configure an HTTP(S) Unity MCP endpoint; use the token field for authentication.")
    token = os.environ.get("UNITY_CONTROLLER_TOKEN")
    headers = {"Authorization": "Bearer " + token} if token else {}
    return Client(StreamableHttpTransport(url, headers=headers, httpx_client_factory=http_client))


def make_proxy(client):
    proxy = create_proxy(client, name="Unity MCP", version="0.7.1")
    # Cage exports external tools and prompts. Surface MCP resources to those
    # clients as well, without interpreting resource URIs or their contents.
    if client.initialize_result.capabilities.resources is not None:
        @proxy.tool
        async def unity_mcp_list_resources(cursor: str | None = None) -> dict:
            """List resources published by the connected Unity MCP service."""
            return (await client.list_resources_mcp(cursor=cursor)).model_dump(mode="json", by_alias=True, exclude_none=True)

        @proxy.tool
        async def unity_mcp_list_resource_templates(cursor: str | None = None) -> dict:
            """List resource URI templates published by the connected Unity MCP service."""
            return (await client.list_resource_templates_mcp(cursor=cursor)).model_dump(mode="json", by_alias=True, exclude_none=True)

        @proxy.tool
        async def unity_mcp_read_resource(uri: str) -> dict:
            """Read an MCP resource from the connected Unity service."""
            return (await client.read_resource_mcp(uri)).model_dump(mode="json", by_alias=True, exclude_none=True)
    return proxy


async def main():
    # One upstream session per stdio client. Upstream set_active_instance persists
    # between tool calls, including changes made after this optional initial selection.
    async with make_client() as client:
        instance = os.environ.get("UNITY_CONTROLLER_INSTANCE", "").strip()
        if instance:
            result = await client.call_tool_mcp("set_active_instance", {"instance": instance})
            selection = result.structuredContent
            if selection is None and result.content and result.content[0].type == "text":
                try:
                    selection = json.loads(result.content[0].text)
                except ValueError:
                    pass
            if result.isError or isinstance(selection, dict) and selection.get("success") is False:
                raise ValueError("Initial Unity instance unavailable. Update or clear the optional instance setting.")

        proxy = make_proxy(client)
        await proxy.run_stdio_async(show_banner=False)


if __name__ == "__main__":
    asyncio.run(main())
