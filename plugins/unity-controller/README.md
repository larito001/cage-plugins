# Unity Controller 0.4.0

Host-side stdio MCP adapter for an existing Unity MCP Streamable HTTP service.
Requires Python 3.10+ available as `python`. No startup dependencies are downloaded.

## Setup

Enable the plugin and host tools in Cage. Set the endpoint, e.g.
`http://127.0.0.1:8083/mcp` (the host loopback, not the isolated environment).
For another machine use HTTPS or an independently configured local SSH tunnel.
Optional Bearer token uses Cage encrypted secret settings. Redirects are disabled;
inherited HTTP proxy variables are ignored.

The instance setting may be empty ONLY to run `unity_controller_instances`.
Copy the returned exact `Name@hash` into the instance setting to enable project
queries. No automatic selection or fallback occurs when an instance is missing.
The hash comes from Unity MCP; do not calculate it yourself.

## Project editing

Connects to an external Unity Editor. Lists instances, reads local project, scripts, shaders, objects, resources, logs, tests, build and package status, rendering, physics and API metadata. Edits scenes, objects, built-in components, prefabs, data assets, materials, textures, cameras, meshes, animation, VFX, physics, UI, lighting, tags and layers. Supports scene repair, undo/redo, clearing logs, project screenshots and batches of up to 20. See Allowed operations for every tool, action and resource.

[Full list of allowed operations](view/index.html). The configured MCP address is the sole upstream. Project editing can invoke callbacks already installed in Unity. Enforce process isolation or an outbound firewall for machine-wide restrictions.
