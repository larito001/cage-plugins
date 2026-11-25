# Unity Controller 0.5.0

Host-side stdio MCP adapter for an existing Unity MCP Streamable HTTP service.
Requires Python 3.10+ available as `python`. No startup dependencies are downloaded.

## Setup

Enable the plugin and host tools in Cage. Set the endpoint, e.g.
`http://127.0.0.1:8083/mcp` (the host loopback, not the isolated environment).
For another machine use HTTPS or an independently configured local SSH tunnel.
Optional Bearer token uses Cage encrypted secret settings. Redirects are disabled;
inherited HTTP proxy variables are ignored.

The instance setting may be empty ONLY to run `unity_controller_instances`.
Copy the returned project hash into the instance setting. Existing exact Name@hash settings also work. Ambiguous or missing selections are rejected.

## Project operations

Edit scenes, objects, built-in components, prefabs, data assets, materials, textures, cameras, meshes, animation clips and controllers, VFX, physics, rendering and UI in a selected external Unity project. Supports scene repair, undo/redo, clearing logs, project-local captures and batches of 20. Returns selected project numbers, IDs and flags. Blocks documents, Blender, host network and application queries, external services and arbitrary code. See the operation list for individual actions.

[Complete operation table](view/index.html). The controller projects upstream results onto a fixed set of numeric project fields and flags. It does not relay raw text, screenshots, registry URLs, application inventories or upstream errors. Screenshot files are saved in the project. Calls into installed Unity editor callbacks still run with Unity’s OS permissions. Other host tools have their own access controls.
