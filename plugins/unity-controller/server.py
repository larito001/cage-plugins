"""Small stdio MCP controller for a separately running Unity MCP HTTP server."""
import json
import os
import re
import sys
import urllib.request
from urllib.parse import urlsplit

LIMIT = 8 * 1024 * 1024
READ = {
    "find_gameobjects": None, "find_in_file": None, "get_sha": None,
    "manage_script_capabilities": None, "get_test_job": None, "validate_script": None,
    "read_console": {"get"},
    "manage_scene": {"get_active", "get_hierarchy", "get_build_settings", "get_loaded_scenes", "validate"},
    "manage_asset": {"search", "get_info", "get_components"},
    "manage_script": {"read"}, "manage_shader": {"read"},
    "manage_material": {"ping", "get_material_info"},
    "manage_prefabs": {"get_info", "get_hierarchy"},
    "manage_camera": {"ping", "list_cameras", "get_brain_status"},
    "manage_animation": {"animator_get_info", "animator_get_parameter", "controller_get_info", "clip_get_info"},
    "manage_vfx": {"particle_get_info", "vfx_get_info", "vfx_list_templates", "vfx_list_assets", "line_get_info", "trail_get_info"},
    "manage_graphics": {"ping", "volume_get_info", "volume_list_effects", "bake_status", "bake_get_settings",
                        "stats_get", "stats_list_counters", "stats_get_memory", "pipeline_get_info",
                        "pipeline_get_settings", "feature_list", "skybox_get"},
    "manage_physics": {"ping", "get_settings", "get_collision_matrix", "get_rigidbody", "raycast", "raycast_all", "linecast", "shapecast", "overlap", "validate"},
    "manage_profiler": {"profiler_status", "get_object_memory", "memory_list_snapshots", "frame_debugger_get_events", "get_frame_timing"},
    "manage_packages": {"ping", "get_package_info", "list_registries", "status"},
    "manage_probuilder": {"ping", "get_mesh_info"},
    "manage_ui": {"ping", "read", "list", "get_visual_tree"},
    "manage_editor": {"telemetry_status"},
    "manage_tools": {"list_groups"},
    "unity_reflect": {"get_type", "get_member", "search"},
    "manage_build": {"status", "platform", "settings", "profiles", "scenes"},
}
# Explicit 10.3 operations. Never derive execution permissions from upstream metadata.
EDIT = {
    "manage_scene": "create load save scene_view_frame close_scene set_active_scene move_to_scene",
    "manage_gameobject": "create modify delete duplicate move_relative look_at",
    "manage_components": "add remove set_property",
    "manage_material": "create set_material_color set_material_shader_property assign_material_to_renderer set_renderer_color",
    "manage_asset": "duplicate move rename delete create_folder",
    "manage_prefabs": "create_from_gameobject modify_contents open_prefab_stage save_prefab_stage close_prefab_stage",
    "manage_texture": "create modify delete create_sprite apply_pattern apply_gradient apply_noise set_import_settings",
    "manage_editor": "set_active_tool add_tag remove_tag add_layer remove_layer undo redo",
    "manage_camera": "screenshot screenshot_multiview ensure_brain create_camera set_target set_priority set_lens set_body set_aim set_noise set_blend force_camera release_override",
    "manage_probuilder": "create_shape create_poly_shape extrude_faces extrude_edges bevel_edges subdivide delete_faces bridge_edges connect_elements detach_faces flip_normals merge_faces combine_meshes merge_objects duplicate_and_flip create_polygon merge_vertices weld_vertices split_vertices move_vertices insert_vertex append_vertices_to_edge select_faces set_face_material set_face_color set_face_uvs convert_to_probuilder set_smoothing auto_smooth center_pivot freeze_transform set_pivot validate_mesh repair_mesh",
    "manage_physics": "set_collision_matrix configure_rigidbody add_joint remove_joint configure_joint assign_physics_material apply_force",
    "manage_graphics": "skybox_set_material skybox_set_properties skybox_set_ambient skybox_set_fog skybox_set_reflection skybox_set_sun feature_toggle feature_reorder",
    "manage_animation": "animator_set_parameter animator_set_speed animator_set_enabled controller_add_state controller_add_transition controller_add_parameter controller_assign controller_add_layer controller_remove_layer controller_set_layer_weight controller_create_blend_tree_1d controller_create_blend_tree_2d controller_add_blend_tree_child clip_assign clip_remove_event",
    "manage_ui": "modify_visual_element attach_ui_document detach_ui_document render_ui",
    "manage_vfx": "particle_create particle_set_main particle_set_emission particle_set_shape particle_set_color_over_lifetime particle_set_size_over_lifetime particle_set_velocity_over_lifetime particle_set_noise particle_set_renderer particle_enable_module line_set_positions line_add_position line_set_position line_set_width line_set_color line_set_material line_set_properties line_clear line_create_line line_create_circle line_create_arc line_create_bezier trail_set_time trail_set_width trail_set_color trail_set_material trail_set_properties trail_clear trail_emit vfx_play vfx_stop vfx_pause vfx_set_playback_speed vfx_set_seed particle_play particle_stop particle_pause particle_restart particle_clear particle_add_burst particle_clear_bursts vfx_set_float vfx_set_int vfx_set_bool vfx_set_vector2 vfx_set_vector3 vfx_set_vector4 vfx_set_color",
    "read_console": "clear",
}
ALLOWED = READ.copy()
for family, names in EDIT.items():
    ALLOWED[family] = (READ.get(family) or set()) | set(names.split())

# Asset database operations can also address code, packages and directories.
# Use typed data files; don't allow a rename to turn data into executable content.
DATA_EXT = {".unity", ".prefab", ".mat", ".png", ".jpg", ".jpeg", ".tga", ".anim", ".controller",
            ".physicmaterial", ".physicsmaterial2d", ".spriteatlas", ".mesh", ".wav", ".mp3", ".ogg"}
COMPONENTS = {
    "Rigidbody": {"mass", "useGravity", "isKinematic", "drag", "angularDrag"},
    "BoxCollider": {"enabled", "isTrigger", "size", "center"},
    "SphereCollider": {"enabled", "isTrigger", "radius", "center"},
    "CapsuleCollider": {"enabled", "isTrigger", "radius", "height", "direction", "center"},
    "Camera": {"enabled", "fieldOfView", "orthographic", "orthographicSize", "depth"},
    "Light": {"enabled", "intensity", "range", "spotAngle"},
    "MeshRenderer": {"enabled"}, "SpriteRenderer": {"enabled", "flipX", "flipY", "sortingOrder"},
    "AudioSource": {"enabled", "volume", "pitch", "mute", "loop"},
}
def asset_path(value, extensions=None):
    if not isinstance(value, str) or not value.startswith("Assets/"):
        raise ValueError("Use a project path beginning with Assets/")
    for part in value.split("/")[1:]:
        if (not re.fullmatch(r"[\w ().-]+", part) or part.startswith(".") or part.endswith((".", " "))
                or part.split(".")[0].upper() in {"CON","NUL","PRN","AUX",*(f"COM{i}" for i in range(10)),*(f"LPT{i}" for i in range(10))}):
            raise ValueError("Invalid asset path")
    if extensions and not any(value.lower().endswith(ext) for ext in extensions):
        raise ValueError("Unsupported asset file type")

def check_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower().replace("_", "") in {"unityinstance","instance","meta","code","url","uri","action","command"}:
                raise ValueError("Nested control fields are disabled")
            check_values(item)
    elif isinstance(value, list):
        for item in value:
            check_values(item)
    elif isinstance(value,str):
        if any(c in value for c in ("\\",":","%","..","//","{","}","[","]","~")) or value.startswith("/") or any(ord(c)<32 for c in value):
            raise ValueError("Use local project values and structured JSON arguments")

def check_edit(tool, a):
    action = a["action"]
    for k,v in a.items():
        if k != "action":
            check_values(v)
    if tool == "manage_asset":
        asset_path(a.get("path"), None if action=="create_folder" else DATA_EXT)
        if action in {"duplicate","move","rename"}:
            asset_path(a.get("destination"), {a["path"][a["path"].rfind("."):].lower()})
    if tool == "manage_texture":
        asset_path(a.get("path"), {".png"})
        if "image_path" in a:
            asset_path(a["image_path"], {".png",".jpg",".jpeg"})
    for key, exts in {"material_path":({".physicmaterial", ".physicsmaterial", ".physicsmaterial2d"} if tool == "manage_physics" else {".mat"}), "prefab_path":{".prefab"}, "scene_path":{".unity"},
                      "controller_path":{".controller"},"clip_path":{".anim"},"source_asset":{".uxml"}, "panel_settings":{".asset"}}.items():
        if key in a:
            asset_path(a[key], exts)
    if tool == "manage_scene" and "name" in a and not re.fullmatch(r"[\w -]+(?:\.unity)?", a["name"]):
        raise ValueError("Use a plain scene name and a separate project path")
    if tool == "manage_scene" and "path" in a:
        asset_path(a["path"])
    if tool == "manage_prefabs" and action not in {"save_prefab_stage","close_prefab_stage"}:
        asset_path(a.get("prefab_path"), {".prefab"})
    if tool in {"manage_gameobject","manage_prefabs"} and set(a) & {"components_to_add","components_to_remove","component_properties","create_child","save_as_prefab","prefab_folder"}:
        raise ValueError("Use the typed component or prefab tool for this edit")
    if tool == "manage_components":
        fields = COMPONENTS.get(a.get("component_type"))
        if fields is None or "properties" in a or ("property" in a and a["property"] not in fields):
            raise ValueError("Only catalogued built-in components and properties may be edited")
        if "value" in a:
            v = a["value"]
            if not isinstance(v,(int,float)) and not (isinstance(v,list) and len(v)<=4 and all(isinstance(n,(int,float)) for n in v)):
                raise ValueError("Use a numeric, boolean, or numeric vector value")
    if action in {"screenshot","screenshot_multiview","render_ui"}:
        if a.get("output_folder","Assets/Screenshots") != "Assets/Screenshots":
            raise ValueError("Capture folder is fixed to Assets/Screenshots")
        if "screenshot_file_name" in a and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}(?:\.png)?", a["screenshot_file_name"]):
            raise ValueError("Use a simple PNG filename")
        a["output_folder"] = "Assets/Screenshots"

RESOURCES = {
    "mcpforunity://editor/state", "mcpforunity://project/info", "mcpforunity://project/tags",
    "mcpforunity://project/layers", "mcpforunity://editor/active-tool", "mcpforunity://editor/selection",
    "mcpforunity://editor/windows", "mcpforunity://editor/prefab-stage", "mcpforunity://scene/cameras",
    "mcpforunity://rendering/stats", "mcpforunity://pipeline/renderer-features",
    "mcpforunity://scene/volumes", "mcpforunity://tool-groups", "mcpforunity://custom-tools",
    "mcpforunity://menu-items", "mcpforunity://scene/gameobject-api", "mcpforunity://prefab-api",
}
RESOURCE_PATTERN = r"mcpforunity://scene/gameobject/-?\d+(?:/components|/component/[A-Za-z_][A-Za-z0-9_.]*)?"


def allowed_resource(uri):
    return isinstance(uri, str) and (uri in RESOURCES or re.fullmatch(RESOURCE_PATTERN, uri) is not None)


def reject_network_references(value):
    if isinstance(value, dict):
        for item in value.values():
            reject_network_references(item)
    elif isinstance(value, list):
        for item in value:
            reject_network_references(item)
    elif isinstance(value, str):
        text = value.removeprefix("mcpforunity://path/Assets/")
        if re.search(r"[a-zA-Z][a-zA-Z0-9+.-]*://|(?:^|[\s\"'])//|\\\\", text):
            raise ValueError("External references are disabled")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Endpoint redirects are disabled")


class Unity:
    def __init__(self, discovery=False):
        self.url = os.environ.get("UNITY_CONTROLLER_URL", "http://127.0.0.1:8083/mcp")
        p = urlsplit(self.url)
        if p.username or p.password or p.query or p.fragment or not p.hostname:
            raise ValueError("Invalid endpoint URL")
        if p.scheme != "https" and not (p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost", "::1")):
            raise ValueError("Use HTTPS for remote endpoints or a local tunnel")
        self.instance = os.environ.get("UNITY_CONTROLLER_INSTANCE", "")
        if not discovery and not re.fullmatch(r"[^@\r\n]+@[0-9a-fA-F]+", self.instance):
            raise ValueError("Configure the exact Unity instance Name@hash")
        self.mode = "project-edit"
        self.token = os.environ.get("UNITY_CONTROLLER_TOKEN", "")
        if "\r" in self.token or "\n" in self.token:
            raise ValueError("Invalid token")
        self.session = None
        self.seq = 0
        # Local endpoints must not be sent to an inherited system proxy.
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def rpc(self, method, params=None, notification=False):
        self.seq += 1
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            msg["id"] = self.seq
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": "2025-03-26"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, json.dumps(msg).encode(), headers)
        with self.http.open(req, timeout=30) as response:
            self.session = response.headers.get("Mcp-Session-Id", self.session)
            if notification:
                return {}
            if "text/event-stream" in response.headers.get("Content-Type", ""):
                size, data = 0, []
                while True:
                    line = response.readline(LIMIT + 1)
                    size += len(line)
                    if size > LIMIT:
                        raise ValueError("Response too large")
                    if not line:
                        break
                    line = line.decode("utf-8").rstrip("\r\n")
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        item = json.loads("\n".join(data))
                        data = []
                        if item.get("id") == msg["id"]:
                            return self.result(item)
                raise ValueError("Missing MCP response")
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError("Response too large")
            item = json.loads(raw)
            if item.get("id") != msg["id"]:
                raise ValueError("Mismatched MCP response")
            return self.result(item)

    @staticmethod
    def result(item):
        if "error" in item:
            raise ValueError("Upstream MCP rejected the request")
        return item.get("result", {})

    def connect(self, discovery=False):
        self.info = self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                            "clientInfo": {"name": "unity-controller", "version": "0.4.0"}})
        self.rpc("notifications/initialized", notification=True)
        raw = self.rpc("resources/read", {"uri": "mcpforunity://instances"})
        instances = []
        for content in raw.get("contents", []):
            if "text" in content:
                instances.extend(json.loads(content["text"]).get("instances", []))
        if discovery:
            return [{k: i.get(k) for k in ("id", "name", "unity_version")} for i in instances]
        if not any(i.get("id") == self.instance for i in instances):
            raise ValueError("Configured Unity instance is not connected; no fallback is allowed")
        selected = self.rpc("tools/call", {"name": "set_active_instance", "arguments": {"instance": self.instance}})
        if selected.get("isError"):
            raise ValueError("Could not select the configured Unity instance")
        # Some releases report domain errors inside successful MCP content.
        for content in selected.get("content", []):
            try:
                value = json.loads(content.get("text", ""))
            except ValueError:
                continue
            if isinstance(value, dict) and (value.get("success") is False or value.get("error")):
                raise ValueError("Could not select the configured Unity instance")

    def close(self):
        if self.session:
            headers = {"Mcp-Session-Id": self.session, "MCP-Protocol-Version": "2025-03-26"}
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
            try:
                with self.http.open(urllib.request.Request(self.url, headers=headers, method="DELETE"), timeout=5):
                    pass
            except Exception:
                pass

    def check(self, tool, arguments):
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")
        # Instance selection belongs to configuration, not to model arguments.
        if any(k in arguments for k in ("unity_instance", "instance", "_meta")):
            raise ValueError("Instance overrides are disabled")
        reject_network_references(arguments)
        if tool not in ALLOWED:
            raise ValueError("Tool is not permitted by the configured access mode")
        if arguments.get("generate_preview") not in (None, False) or arguments.get("generatePreview") not in (None, False):
            raise ValueError("Preview generation is disabled")
        if tool == "manage_asset":
            arguments["generate_preview"] = False
        if tool == "manage_profiler" and "search_path" in arguments:
            raise ValueError("Use the default project snapshot folder")
        if tool == "manage_build" and set(arguments) - {"action", "job_id", "property"}:
            raise ValueError("Only build information queries are permitted")
        if tool == "manage_scene" and arguments.get("action") == "validate":
            if "autoRepair" in arguments or type(arguments.get("auto_repair", False)) is not bool:
                raise ValueError("Use the boolean auto_repair field")
        if tool == "validate_script" and arguments.get("level", "basic") not in ("basic", "standard"):
            raise ValueError("Only basic or standard syntax checks are permitted")
        if tool in {"find_in_file", "get_sha", "validate_script"} and "uri" in arguments:
            uri = arguments["uri"]
            if not isinstance(uri, str):
                raise ValueError("Use a script path under Assets/")
            asset_path(uri.removeprefix("mcpforunity://path/"), {".cs"})
        if tool in {"manage_script", "manage_shader"}:
            directory = arguments.get("path", "Assets/")
            if not isinstance(directory, str):
                raise ValueError("Use a directory under Assets/")
            asset_path(directory.rstrip("/") + "/placeholder")
            if "name" in arguments:
                name = arguments["name"]
                if not isinstance(name, str) or "/" in name:
                    raise ValueError("Use a filename and a separate project path")
                asset_path("Assets/" + name)
        actions = ALLOWED[tool]
        if actions is not None and arguments.get("action") not in actions:
            raise ValueError("An explicitly permitted action is required")
        if arguments.get("action") in EDIT.get(tool, "").split():
            check_edit(tool, arguments)


def text_result(value):
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}


def tool(name, description, properties=None, required=None):
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}


TOOLS = [
    tool("unity_controller_batch", "Execute up to 20 project operations sequentially. All requests are validated before connecting; any disallowed operation rejects the entire batch.",
         {"calls": {"type": "array", "minItems": 1, "maxItems": 20, "items": {
             "type": "object", "properties": {"tool": {"type": "string"}, "arguments": {"type": "object"}},
             "required": ["tool", "arguments"], "additionalProperties": False}}}, ["calls"]),
    tool("unity_controller_instances", "List connected Unity project names and exact Name@hash identifiers without selecting a project."),
    tool("unity_controller_status", "Read the connection status and the configured Unity Editor instance."),
    tool("unity_controller_catalog", "List permitted Unity operations and their argument schemas. Only explicitly permitted project actions are available."),
    tool("unity_controller_read", "Read editor, project, camera or object/component information from the configured Unity instance.",
         {"uri": {"type": "string", "description": "Use a URI from the catalog, including scene/gameobject/{id} and its components."}}, ["uri"]),
    tool("unity_controller_call", "Invoke a permitted Unity operation on the configured instance. May change or delete project data.",
         {"tool": {"type": "string"}, "arguments": {"type": "object"}}, ["tool", "arguments"]),
]


def call(name, args):
    schema = next((t["inputSchema"] for t in TOOLS if t["name"] == name), None)
    if schema is None or not isinstance(args, dict) or set(args) - set(schema["properties"]) or set(schema["required"]) - set(args):
        raise ValueError("Unknown tool or invalid arguments")
    discovery = name == "unity_controller_instances"
    client = Unity(discovery=discovery)
    # Validate the entire batch before any upstream call; never proxy batch_execute.
    if name == "unity_controller_batch":
        calls = args["calls"]
        if not isinstance(calls, list) or not 1 <= len(calls) <= 20:
            raise ValueError("Batch must contain 1 to 20 queries")
        for item in calls:
            if not isinstance(item, dict) or set(item) != {"tool", "arguments"}:
                raise ValueError("Invalid batch item")
            client.check(item["tool"], item["arguments"])
    # Validate locally before establishing any network connection.
    if name == "unity_controller_call":
        client.check(args["tool"], args["arguments"])
    if name == "unity_controller_read" and not allowed_resource(args["uri"]):
        raise ValueError("Resource is not permitted")
    try:
        if discovery:
            return text_result({"instances": client.connect(discovery=True)})
        client.connect()
        if name == "unity_controller_batch":
            results, size = [], 0
            for item in calls:
                result = client.rpc("tools/call", {"name": item["tool"], "arguments": item["arguments"]})
                size += len(json.dumps(result).encode("utf-8"))
                if size > LIMIT:
                    raise ValueError("Batch response too large; use smaller batches")
                results.append({"tool": item["tool"], "result": result})
                if result.get("isError"):
                    break
            return text_result({"results": results, "completed": len(results), "requested": len(calls)})
        if name == "unity_controller_status":
            return text_result({"connected": True, "instance": client.instance, "mode": client.mode,
                                "server": client.info.get("serverInfo")})
        if name == "unity_controller_catalog":
            result, permitted, cursor = {}, [], None
            for _ in range(16):
                result = client.rpc("tools/list", {"cursor": cursor} if cursor else {})
                for t in result.get("tools", []):
                    n = t.get("name")
                    if n in ALLOWED:
                        # Return schemas as data, never register unreviewed upstream tools.
                        schema = t.get("inputSchema", {})
                        if ALLOWED[n]:
                            schema.setdefault("properties", {})["action"] = {"type": "string", "enum": sorted(ALLOWED[n])}
                            schema["required"] = sorted(set(schema.get("required", [])) | {"action"})
                        permitted.append({"name": n, "inputSchema": schema,
                                          "allowed_actions": sorted(ALLOWED[n]) if ALLOWED[n] else None})
                cursor = result.get("nextCursor")
                if not cursor:
                    break
            return text_result({"mode": client.mode, "tools": permitted, "resources": sorted(RESOURCES),
                                "resource_templates": ["mcpforunity://scene/gameobject/{id}", "mcpforunity://scene/gameobject/{id}/components", "mcpforunity://scene/gameobject/{id}/component/{type}" ]})
        if name == "unity_controller_read":
            return text_result(client.rpc("resources/read", {"uri": args["uri"]}))
        return client.rpc("tools/call", {"name": args["tool"], "arguments": args["arguments"]})
    finally:
        client.close()


def main():
    for line in sys.stdin.buffer:
        msg = {}
        try:
            if len(line) > LIMIT:
                raise ValueError("Request too large")
            msg = json.loads(line)
            if "id" not in msg:
                continue
            method = msg.get("method")
            if method == "initialize":
                result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                          "serverInfo": {"name": "unity-controller", "version": "0.4.0"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                try:
                    p = msg.get("params", {})
                    result = call(p.get("name"), p.get("arguments", {}))
                except Exception as exc:
                    # Network exceptions may contain secret endpoints; never echo them.
                    message = str(exc) if isinstance(exc, ValueError) else "Unity connection failed; check endpoint, credentials and server state"
                    result = {"isError": True, "content": [{"type": "text", "text": message}]}
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Method not supported"}}), flush=True)
                continue
            print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
        except Exception:
            print(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32600, "message": "Invalid request"}}), flush=True)


if __name__ == "__main__":
    main()
