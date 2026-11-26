"""Small stdio MCP controller for a separately running Unity MCP HTTP server."""
import json
import math
from pathlib import Path
import os
import re
import sys
import threading

import menu_review
import urllib.request
from urllib.parse import urlsplit

LIMIT = 8 * 1024 * 1024
READ = {
    "find_gameobjects": None,
    "manage_scene": {"get_active", "get_hierarchy", "get_build_settings", "get_loaded_scenes", "validate"},
    "manage_asset": {"search", "get_info"},
    "manage_material": {"ping", "get_material_info"},
    "manage_prefabs": {"get_info", "get_hierarchy"},
    "manage_camera": {"ping", "list_cameras", "get_brain_status"},
    "manage_animation": {"animator_get_info", "animator_get_parameter", "controller_get_info", "clip_get_info"},
    "manage_vfx": {"particle_get_info", "vfx_get_info", "vfx_list_templates", "vfx_list_assets", "line_get_info", "trail_get_info"},
    "manage_graphics": {"ping", "volume_get_info", "volume_list_effects", "bake_status", "bake_get_settings",
                        "stats_get", "stats_list_counters", "stats_get_memory", "pipeline_get_info",
                        "pipeline_get_settings", "feature_list", "skybox_get"},
    "manage_physics": {"ping", "get_settings", "get_collision_matrix", "get_rigidbody", "raycast", "raycast_all", "linecast", "shapecast", "overlap", "validate"},
    "manage_profiler": {"profiler_status", "get_object_memory", "get_frame_timing"},
    "manage_probuilder": {"ping", "get_mesh_info"},
    "manage_ui": {"ping", "get_visual_tree"},
    "manage_build": {"status", "platform", "profiles", "scenes"},
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
    "manage_camera": "screenshot screenshot_multiview ensure_brain create_camera set_target set_priority set_lens set_body set_aim add_extension remove_extension set_noise set_blend force_camera release_override",
    "manage_probuilder": "create_shape create_poly_shape extrude_faces extrude_edges bevel_edges subdivide delete_faces bridge_edges connect_elements detach_faces flip_normals merge_faces combine_meshes merge_objects duplicate_and_flip create_polygon merge_vertices weld_vertices split_vertices move_vertices insert_vertex append_vertices_to_edge select_faces set_face_material set_face_color set_face_uvs convert_to_probuilder set_smoothing auto_smooth center_pivot freeze_transform set_pivot validate_mesh repair_mesh",
    "manage_physics": "set_collision_matrix configure_rigidbody add_joint remove_joint configure_joint assign_physics_material apply_force set_settings create_physics_material configure_physics_material",
    "manage_graphics": "skybox_set_material skybox_set_properties skybox_set_ambient skybox_set_fog skybox_set_reflection skybox_set_sun feature_toggle feature_reorder pipeline_set_quality stats_set_scene_debug bake_set_settings bake_create_light_probe_group bake_create_reflection_probe bake_set_probe_positions volume_set_properties volume_create_profile",
    "manage_animation": "animator_set_parameter animator_set_speed animator_set_enabled controller_add_state controller_add_transition controller_add_parameter controller_assign controller_add_layer controller_remove_layer controller_set_layer_weight controller_create_blend_tree_1d controller_create_blend_tree_2d controller_add_blend_tree_child clip_assign clip_remove_event clip_create clip_create_preset controller_create clip_add_curve clip_set_curve clip_set_vector_curve",
    "manage_ui": "modify_visual_element attach_ui_document detach_ui_document render_ui create_panel_settings update_panel_settings",
    "manage_vfx": "particle_create particle_set_main particle_set_emission particle_set_shape particle_set_color_over_lifetime particle_set_size_over_lifetime particle_set_velocity_over_lifetime particle_set_noise particle_set_renderer particle_enable_module line_set_positions line_add_position line_set_position line_set_width line_set_color line_set_material line_set_properties line_clear line_create_line line_create_circle line_create_arc line_create_bezier trail_set_time trail_set_width trail_set_color trail_set_material trail_set_properties trail_clear trail_emit vfx_play vfx_stop vfx_pause vfx_set_playback_speed vfx_set_seed particle_play particle_stop particle_pause particle_restart particle_clear particle_add_burst particle_clear_bursts vfx_set_float vfx_set_int vfx_set_bool vfx_set_vector2 vfx_set_vector3 vfx_set_vector4 vfx_set_color vfx_set_gradient vfx_set_curve",
    "read_console": "clear",
    "manage_profiler": "frame_debugger_enable frame_debugger_disable",
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
    props = a.get("properties", {})
    if tool in {"manage_animation", "manage_camera", "manage_vfx"} and not isinstance(props, dict):
        raise ValueError("Use structured properties")
    if tool == "manage_animation":
        for key in props:
            if key.replace("_", "").lower() in {"clippath", "controllerpath"}:
                raise ValueError("Supply the typed top-level animation asset path")
        if action.startswith("clip_") and action in {"clip_create", "clip_create_preset", "clip_add_curve", "clip_set_curve", "clip_set_vector_curve"}:
            asset_path(a.get("clip_path"), {".anim"})
        if action == "controller_create":
            asset_path(a.get("controller_path"), {".controller"})
        if action in {"clip_add_curve", "clip_set_curve", "clip_set_vector_curve"}:
            if set(props) - {"type","property","propertyPath","relativePath","keys"} or props.get("type","Transform") != "Transform":
                raise ValueError("Curves may target only a Transform")
            fields = [props[k] for k in ("property","propertyPath") if k in props]
            if not fields or not all(isinstance(f, str) and re.fullmatch(
                    r"(?:m_LocalPosition|localPosition|m_LocalRotation|localRotation|localEulerAngles|m_LocalScale|localScale)(?:\.[xyzw])?", f) for f in fields):
                raise ValueError("Use a position, rotation or scale curve")
    if tool == "manage_camera" and action in {"set_body", "set_aim", "add_extension", "remove_extension"}:
        camera_types = {
            "set_body": ("bodyType", {"CinemachineFollow", "CinemachineThirdPersonFollow", "CinemachinePositionComposer"}),
            "set_aim": ("aimType", {"CinemachineRotationComposer", "CinemachineHardLookAt"}),
            "add_extension": ("extensionType", {"CinemachineConfiner2D", "CinemachineConfiner3D", "CinemachineDeoccluder"}),
            "remove_extension": ("extensionType", {"CinemachineConfiner2D", "CinemachineConfiner3D", "CinemachineDeoccluder"}),
        }
        field, types = camera_types[action]
        snake = re.sub(r"([A-Z])", r"_\1", field).lower()
        value = props.get(field, props.get(snake))
        if len(props) != 1 or value not in types:
            raise ValueError("Choose a supported built-in Cinemachine type")
        a["properties"] = {field: "Unity.Cinemachine." + value}
    if tool == "manage_physics" and action == "create_physics_material":
        asset_path(a.get("path", "Assets/Physics Materials") + "/folder")
        if not re.fullmatch(r"[\w -]+", a.get("name") or ""):
            raise ValueError("Use a simple physics material name")
    if tool == "manage_physics" and action == "configure_physics_material":
        asset_path(a.get("path"), {".physicmaterial", ".physicsmaterial", ".physicsmaterial2d"})
    if tool == "manage_graphics" and action == "volume_create_profile":
        asset_path(a.get("path"), {".asset"})
    if tool == "manage_ui" and action in {"create_panel_settings", "update_panel_settings"}:
        asset_path(a.get("path"), {".asset"})
        if set(a.get("settings", {})) - {"scaleMode","referenceDpi","fallbackDpi","sortingOrder","targetDisplay","referenceResolution","scale"}:
            raise ValueError("Only panel layout and display settings are supported")
    if tool == "manage_ui" and "path" in a and action == "render_ui":
        asset_path(a["path"], {".uxml"})
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
        a["include_image"] = False

RESOURCES = {
    "mcpforunity://scene/cameras", "mcpforunity://editor/selection",
    "mcpforunity://rendering/stats", "mcpforunity://scene/volumes",
}
RESOURCE_PATTERN = r"mcpforunity://scene/gameobject/-?\d+"

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
        if not discovery and not re.fullmatch(r"(?:[^@\r\n]+@)?[0-9a-fA-F]+", self.instance):
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
                            "clientInfo": {"name": "unity-controller", "version": "0.6.0"}})
        self.rpc("notifications/initialized", notification=True)
        raw = self.rpc("resources/read", {"uri": "mcpforunity://instances"})
        instances = []
        for content in raw.get("contents", []):
            if "text" in content:
                instances.extend(json.loads(content["text"]).get("instances", []))
        if discovery:
            return [{"id": i["id"].rsplit("@", 1)[1]} for i in instances
                    if re.fullmatch(r"[^@\r\n]+@[a-fA-F0-9]+", i.get("id") or "")]
        matches = [i.get("id") for i in instances
                   if i.get("id") == self.instance or
                   ("@" not in self.instance and (i.get("id") or "").endswith("@" + self.instance))]
        if len(matches) != 1:
            raise ValueError("Configured Unity instance is missing or ambiguous")
        selected = self.rpc("tools/call", {"name": "set_active_instance", "arguments": {"instance": matches[0]}})
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
        if set(arguments) - SCHEMAS[tool]["properties"].keys():
            raise ValueError("Unknown argument for this tool")
        if tool == "manage_build" and set(arguments) - {"action", "job_id"}:
            raise ValueError("Only build information queries are permitted")
        if tool == "manage_scene" and arguments.get("action") == "validate":
            if type(arguments.get("auto_repair", False)) is not bool:
                raise ValueError("Use the boolean auto_repair field")
        for key, value in arguments.items():
            if key != "action":
                check_values(value)
        if tool == "manage_prefabs" and "prefab_path" in arguments:
            asset_path(arguments["prefab_path"], {".prefab"})
        if tool == "manage_material" and "material_path" in arguments:
            asset_path(arguments["material_path"], {".mat"})
        if tool == "manage_animation":
            for key, ext in (("clip_path", ".anim"), ("controller_path", ".controller")):
                if key in arguments:
                    asset_path(arguments[key], {ext})
        if tool == "manage_profiler" and "object_path" in arguments:
            obj = arguments["object_path"]
            if arguments.get("action") != "get_object_memory" or not isinstance(obj, str):
                raise ValueError("Use a project object for memory queries")
            if obj.startswith("Assets/"):
                asset_path(obj, DATA_EXT)
            elif not re.fullmatch(r"[\w -]+(?:/[\w -]+)*", obj):
                raise ValueError("Use a scene hierarchy path or supported project asset")
        if tool == "manage_graphics" and "profile_path" in arguments:
            asset_path(arguments["profile_path"], {".asset"})
        if tool == "manage_asset" and arguments.get("action") == "get_info":
            asset_path(arguments.get("path"), DATA_EXT)
        if tool == "manage_asset" and arguments.get("action") == "search":
            folder = arguments.get("path", "Assets")
            if folder != "Assets":
                raise ValueError("Asset search is scoped to Assets")
            kind = arguments.setdefault("filter_type", "Prefab")
            if kind not in {"Prefab", "SceneAsset", "Material", "Texture2D", "Mesh", "AnimationClip",
                            "AnimatorController", "AudioClip", "Sprite"} or not re.fullmatch(
                                r"[\w -]*", arguments.get("search_pattern") or ""):
                raise ValueError("Search by a plain name and a supported project asset type")
            arguments["path"] = folder
        actions = ALLOWED[tool]
        if actions is not None and arguments.get("action") not in actions:
            raise ValueError("An explicitly permitted action is required")
        if arguments.get("action") in EDIT.get(tool, "").split():
            check_edit(tool, arguments)


SCHEMAS = json.loads(Path(__file__).with_name("schemas.json").read_text(encoding="utf-8"))


def text_result(value):
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}


# Copy only the project fields that the controller presents to its client.
# Free text, blobs, host paths and arbitrary component/property maps stay upstream.
PROJECT_NUMBERS = frozenset("""
    activeInstanceID eventCount draw_calls set_pass_calls dynamic_batches static_batches
    instanced_batches shadow_casters render_textures render_textures_bytes used_textures
    used_textures_bytes render_target_changes visible_skinned_meshes sizeBytes memoryBytes
    id instanceID instanceId instance_id parentId parentInstanceID buildIndex rootCount
    childCount depth count total totalCount pageSize pageNumber nextCursor next_cursor
    layer priority fieldOfView orthographicSize mass intensity range frameRate duration
    width height vertexCount triangleCount subMeshCount particleCount stateCount layerCount
    drawCalls batches triangles vertices cameraCount index order weight
""".split())
PROJECT_FLAGS = frozenset("""
    hasBrain cinemachineInstalled isDirty isLoaded isActive activeSelf activeInHierarchy enabled isTrigger
    isKinematic useGravity orthographic hasMore has_more visible
""".split())
PROJECT_GROUPS = frozenset("""
    activeGameObject activeTransform brain unityCameras cinemachineCameras
    items children hierarchy roots objects gameObjects cameras scenes volumes
    results instances instanceIDs instance_ids gameobjects transform stats
""".split())
PROJECT_VECTORS = {"position", "rotation", "localPosition", "localRotation", "scale",
                   "localScale", "eulerAngles", "bounds", "center", "size", "color"}

def number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))

def project_fields(value):
    if isinstance(value, list):
        return [project_fields(item) if isinstance(item, dict) else item
                for item in value if isinstance(item, dict) or number(item)]
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, item in value.items():
        if key in PROJECT_NUMBERS and number(item):
            result[key] = item
        elif key in PROJECT_FLAGS and type(item) is bool:
            result[key] = item
        elif key in PROJECT_GROUPS and isinstance(item, (dict, list)):
            result[key] = project_fields(item)
        elif key in PROJECT_VECTORS:
            if isinstance(item, dict):
                result[key] = {axis: item[axis] for axis in "xyzwrgba" if number(item.get(axis))}
            elif isinstance(item, list) and len(item) <= 4 and all(number(v) for v in item):
                result[key] = item
    return result


def project_reply(raw, resource=False):
    if raw.get("isError"):
        return {"isError": True, **text_result({"success": False})}
    value = raw.get("structuredContent")
    if not isinstance(value, dict):
        blocks = raw.get("contents" if resource else "content", [])
        try:
            value = json.loads(next(b["text"] for b in blocks if isinstance(b.get("text"), str)))
        except (StopIteration, ValueError):
            value = None
    if not isinstance(value, dict) or value.get("success") is False or value.get("error"):
        return {"isError": True, **text_result({"success": False})}
    data = project_fields(value.get("data", value))
    return text_result({"success": True, "data": data})


def tool(name, description, properties=None, required=None):
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}


MENU_TOOL = "unity_controller_execute_menu"

TOOLS = [
    tool(MENU_TOOL, "Request one Unity Editor menu action by its exact path. A fresh confirmation on the controller host is required for every call. Independent of build permissions. A dispatch acknowledgment does not verify its output.",
         {"menu_path": {"type": "string", "minLength": 3, "maxLength": 240}}, ["menu_path"]),
    tool("unity_controller_batch", "Execute up to 20 project operations sequentially. All requests are validated before connecting; any disallowed operation rejects the entire batch.",
         {"calls": {"type": "array", "minItems": 1, "maxItems": 20, "items": {
             "type": "object", "properties": {"tool": {"type": "string"}, "arguments": {"type": "object"}},
             "required": ["tool", "arguments"], "additionalProperties": False}}}, ["calls"]),
    tool("unity_controller_instances", "List the hashes of connected Unity projects without selecting a project."),
    tool("unity_controller_status", "Read the connection status and the configured Unity Editor instance."),
    tool("unity_controller_catalog", "List permitted Unity operations and their argument schemas. Only explicitly permitted project actions are available."),
    tool("unity_controller_read", "Read editor, project, camera or object/component information from the configured Unity instance.",
         {"uri": {"type": "string", "description": "Use a URI from the catalog, including scene/gameobject/{id}."}}, ["uri"]),
    tool("unity_controller_call", "Invoke a permitted Unity operation on the configured instance. May change or delete project data.",
         {"tool": {"type": "string"}, "arguments": {"type": "object"}}, ["tool", "arguments"]),
]


def call(name, args, cancelled=None):
    schema = next((t["inputSchema"] for t in TOOLS if t["name"] == name), None)
    if schema is None or not isinstance(args, dict) or set(args) - set(schema["properties"]) or set(schema["required"]) - set(args):
        raise ValueError("Unknown tool or invalid arguments")
    discovery = name == "unity_controller_instances"
    client = Unity(discovery=discovery)
    if name == MENU_TOOL:
        path = args["menu_path"]
        menu_review.validate_path(path)
        cancelled = cancelled if cancelled is not None else threading.Event()
        if not menu_review.ask_once(client.instance, path, cancelled) or cancelled.is_set():
            return {"isError": True, **text_result({"message": menu_review.DENIED})}
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
        if name == MENU_TOOL:
            if cancelled.is_set():
                return {"isError": True, **text_result({"message": menu_review.DENIED})}
            try:
                reply = client.rpc("tools/call", {"name": "execute_menu_item", "arguments": {"menu_path": path}})
            except Exception:
                return {"isError": True, **text_result({"message": "Dispatch outcome unknown. Check Unity before requesting another execution."})}
            return project_reply(reply)
        if name == "unity_controller_batch":
            results, size = [], 0
            for item in calls:
                result = project_reply(client.rpc("tools/call", {"name": item["tool"], "arguments": item["arguments"]}))
                size += len(json.dumps(result).encode("utf-8"))
                if size > LIMIT:
                    raise ValueError("Batch response too large; use smaller batches")
                results.append({"tool": item["tool"], "result": result})
                if result.get("isError"):
                    break
            return text_result({"results": results, "completed": len(results), "requested": len(calls)})
        if name == "unity_controller_status":
            return text_result({"connected": True, "instance": client.instance.rsplit("@", 1)[-1], "mode": client.mode})
        if name == "unity_controller_catalog":
            result, permitted, cursor = {}, [], None
            for _ in range(16):
                result = client.rpc("tools/list", {"cursor": cursor} if cursor else {})
                for t in result.get("tools", []):
                    n = t.get("name")
                    if n in ALLOWED:
                        # Return schemas as data, never register unreviewed upstream tools.
                        schema = dict(SCHEMAS[n], properties=SCHEMAS[n]["properties"].copy())
                        if ALLOWED[n]:
                            schema.setdefault("properties", {})["action"] = {"type": "string", "enum": sorted(ALLOWED[n])}
                            schema["required"] = sorted(set(schema.get("required", [])) | {"action"})
                        permitted.append({"name": n, "inputSchema": schema,
                                          "allowed_actions": sorted(ALLOWED[n]) if ALLOWED[n] else None})
                cursor = result.get("nextCursor")
                if not cursor:
                    break
            return text_result({"mode": client.mode, "reviewed_menu_tool": MENU_TOOL, "tools": permitted, "resources": sorted(RESOURCES),
                                "resource_templates": ["mcpforunity://scene/gameobject/{id}" ]})
        if name == "unity_controller_read":
            return project_reply(client.rpc("resources/read", {"uri": args["uri"]}), resource=True)
        return project_reply(client.rpc("tools/call", {"name": args["tool"], "arguments": args["arguments"]}))
    finally:
        client.close()


def tool_result(params, cancelled=None):
    try:
        return call(params.get("name"), params.get("arguments", {}), cancelled)
    except Exception:
        # Transport errors may include the private address or response contents.
        return {"isError": True, **text_result({"message": "Request rejected or Unity unavailable; check the permitted operations and project settings"})}


def main():
    output_lock = threading.Lock()
    def send(request_id, **payload):
        with output_lock:
            print(json.dumps({"jsonrpc": "2.0", "id": request_id, **payload}), flush=True)

    def reviewed_call(request_id, params, cancelled):
        result = tool_result(params, cancelled)
        if not cancelled.is_set():
            send(request_id, result=result)

    # Keep reading cancellation notifications and EOF while the person decides.
    # Overlapping menu calls are refused instead of queuing stale prompts.
    review = None
    try:
        for line in sys.stdin.buffer:
            msg = {}
            try:
                if len(line) > LIMIT:
                    raise ValueError("Request too large")
                msg = json.loads(line)
                method = msg.get("method")
                if "id" not in msg:
                    if method == "notifications/cancelled" and review and msg.get("params", {}).get("requestId") == review[0]:
                        review[1].set()
                    continue
                request_id = msg["id"]
                if method == "initialize":
                    result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                              "serverInfo": {"name": "unity-controller", "version": "0.6.0"}}
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {"tools": TOOLS}
                elif method == "tools/call":
                    params = msg.get("params", {})
                    if params.get("name") == MENU_TOOL:
                        if review and review[2].is_alive():
                            result = {"isError": True, **text_result({"message": "A menu request is already pending"})}
                        else:
                            cancelled = threading.Event()
                            worker = threading.Thread(target=reviewed_call, args=(request_id, params, cancelled), daemon=True)
                            review = (request_id, cancelled, worker)
                            worker.start()
                            continue
                    elif review and review[2].is_alive():
                        result = {"isError": True, **text_result({"message": "Wait for the pending menu request"})}
                    else:
                        result = tool_result(params)
                else:
                    send(request_id, error={"code": -32601, "message": "Method not supported"})
                    continue
                send(request_id, result=result)
            except (ValueError, TypeError, AttributeError):
                send(msg.get("id") if isinstance(msg, dict) else None, error={"code": -32600, "message": "Invalid request"})
    finally:
        if review:
            review[1].set()
            review[2].join(timeout=1)


if __name__ == "__main__":
    main()
