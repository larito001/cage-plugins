"""Regression tests for native MCP discovery, session state and unmodified results."""
import unittest

from fastmcp import Client, FastMCP
from fastmcp.server.context import Context
from fastmcp.tools.tool import ToolResult
from mcp.types import ImageContent, TextContent

from server import make_proxy


class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_tools_session_and_results(self):
        upstream = FastMCP("Test editor")

        @upstream.tool
        async def choose_project(name: str, ctx: Context) -> str:
            await ctx.set_state("project", name)
            return name

        @upstream.tool
        async def sample_result(ctx: Context) -> ToolResult:
            name = await ctx.get_state("project")
            return ToolResult(
                content=[TextContent(type="text", text=name),
                         ImageContent(type="image", mimeType="image/png", data="AQID")],
                structured_content={"project": name, "path": "Assets/Scenes/Main.unity"},
                is_error=False,
            )

        @upstream.resource("unity://test/{project}")
        def test_resource(project: str) -> str:
            return project

        @upstream.prompt
        def project_prompt(label: str) -> str:
            return f"Inspect {label}"

        async with Client(upstream) as backend, Client(make_proxy(backend)) as connector:
            original = {t.name: t.inputSchema for t in await backend.list_tools()}
            tools = {t.name: t.inputSchema for t in await connector.list_tools()}
            for name, schema in original.items():
                self.assertEqual(tools[name], schema)
            await connector.call_tool("choose_project", {"name": "Example"})
            proxied = await connector.call_tool_mcp("sample_result", {})
            direct = await backend.call_tool_mcp("sample_result", {})
            self.assertEqual(proxied.content, direct.content)
            self.assertEqual(proxied.structuredContent, direct.structuredContent)
            self.assertEqual(proxied.structuredContent["project"], "Example")
            templates = await connector.call_tool("unity_mcp_list_resource_templates", {})
            self.assertIn("unity://test/{project}", str(templates.structured_content))
            resource = await connector.call_tool("unity_mcp_read_resource", {"uri": "unity://test/Example"})
            self.assertEqual(resource.structured_content["contents"][0]["text"], "Example")
            self.assertIn("project_prompt", [p.name for p in await connector.list_prompts()])


if __name__ == "__main__":
    unittest.main()
