# Unity Controller 0.2.1

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

## Read-only operations

Call `unity_controller_catalog` for the allowed operations, filtered argument
schemas and resource URIs, then `unity_controller_call` or `unity_controller_read`.
Queries cover objects/components, scenes, assets, scripts/shaders, materials,
prefabs, cameras, animations, VFX, graphics, physics, profiler status/memory,
packages, ProBuilder, UI Toolkit, tool groups, reflection and Unity documentation.
Only explicitly enumerated read actions are permitted, checked on every call.
Asset preview generation is forced off. Unknown future actions fail closed.
`unity_controller_instances` returns only project IDs/names and Unity versions.

Writes, full-control mode, arbitrary C#, custom tools, raw batches, menu execution,
play mode, test execution, import/refresh/compile, package installation and tool
visibility changes are blocked. Screenshots and UI rendering are excluded because
the upstream implementation writes image files or changes render state. Querying
an existing test job is allowed; starting a test run is not. Old full-control
settings cannot re-enable writes in this version.

## Boundary

This filters the documented upstream operations, not all filesystem writes by
Unity. Unity and the MCP service may write their normal logs/caches, and some
queries access the registry/documentation network. It is not an OS sandbox and
does not constrain other clients, the commands plugin or project callbacks.
Returned project data may include file paths or upstream-provided details.

## Validation

`python -m unittest -v test_server.py`

Tested with MCP for Unity 10.3.0 and Unity 2022.3.62f3c1. Availability also depends
on the upstream enabled tool groups. No mutations are used for live testing.
Non-Chinese locales currently use the English description.
