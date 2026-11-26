# Unity MCP

Connect an existing Unity MCP Streamable HTTP service to the host tool catalog. The stable marketplace ID `unity-controller` preserves upgrades, the endpoint and the stored bearer token.

1. Start the Unity MCP service and connect the intended editor.
2. Set **Unity MCP URL** to the service endpoint including its MCP path. The default is `http://127.0.0.1:8083/mcp` on the machine running the connector. Use HTTPS for a remote service carrying credentials.
3. Optionally save a bearer token, then choose a connected project from the initial instance dropdown. Refresh the list after connecting another editor. An empty instance uses the service default. A configured instance is selected once at startup. To change projects later, use the upstream instance-selection tool.
4. Reload plugins after changing connection settings or the service’s tool catalog. The client needs `uv` on PATH; the first start resolves the pinned FastMCP package and caches it. If a cold install exceeds the client startup deadline, reload after dependencies are available.

The connector exposes the upstream tool names and schemas, prompts and results, including structured data and images. For clients that only surface tools, it also provides resource listing, template listing and resource reading tools. The upstream service determines the available operations. When it offers code execution, menu callbacks, document lookup or Blender, those tools can use the editor machine’s permissions. The connector adds no tool allowlist, output redaction or menu approval. The host application's normal plugin authorization and the service's own authentication still apply.
