# Unity Controller 0.6.0

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

Edit a selected external Unity project, including scenes, objects, built-in components, assets, animation, physics, rendering and UI. Supports repair, undo/redo, clearing logs, project-local captures and batches of 20. A separate tool runs an Editor menu by path after a fresh host confirmation for that call. Approved callbacks inherit Unity's file, network and process permissions. Direct document and Blender tools remain blocked. Returns selected project IDs, numbers and flags. See the full operation list.

## Reviewed Unity menus

Call `unity_controller_execute_menu` with one `menu_path`, for example `File/Save Project`. Each call asks on the interactive desktop of the computer running this controller. The dialog shows the configured project identifier and exact menu path. The allow button approves only that invocation. On Windows it checks input origin for the press and release, rejecting ordinary injected clicks and programmatic button invocation. No, cancellation before dispatch, closing the dialog, a 90-second timeout or a missing Python Tk desktop prevents dispatch. There is no caller-supplied approval flag or saved menu grant. The raw menu tool cannot be called through the batch or ordinary project tool. A host with direct desktop-input automation must keep that automation away from the review window; this is an interactive review, not identity verification.

The controller rejects direct document/Blender tools and recognizable documentation or external-application menu paths. Custom labels cannot establish what a callback actually does. Once approved, callbacks can use all permissions of the selected editor. Acknowledgment only covers menu dispatch. After a lost response, check Unity before retrying; a build can continue after a timeout.

[Complete operation table](view/index.html). The controller projects upstream results onto a fixed set of numeric project fields and flags. It does not relay raw text, screenshots, registry URLs, application inventories or upstream errors. Screenshot files are saved in the project. Calls into installed Unity editor callbacks still run with Unity’s OS permissions. Other host tools have their own access controls.
