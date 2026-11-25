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
    "manage_script_capabilities": None, "get_test_job": None,
    "read_console": {"get"},
    "manage_scene": {"get_active", "get_hierarchy", "get_build_settings", "get_loaded_scenes"},
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
    "manage_physics": {"ping", "get_settings", "get_collision_matrix", "get_rigidbody", "raycast", "raycast_all", "linecast", "shapecast", "overlap"},
    "manage_profiler": {"profiler_status", "get_object_memory", "memory_list_snapshots"},
    "manage_packages": {"ping", "list_packages", "search_packages", "get_package_info", "list_registries", "status"},
    "manage_probuilder": {"ping", "get_mesh_info"},
    "manage_ui": {"ping", "read", "list", "get_visual_tree"},
    "manage_editor": {"telemetry_status"},
    "manage_tools": {"list_groups"},
    "unity_reflect": {"get_type", "get_member", "search"},
    "unity_docs": {"get_doc", "get_manual", "get_package_doc", "lookup"},
}
RESOURCES = {
    "mcpforunity://editor/state", "mcpforunity://project/info", "mcpforunity://project/tags",
    "mcpforunity://project/layers", "mcpforunity://editor/active-tool", "mcpforunity://editor/selection",
    "mcpforunity://editor/windows", "mcpforunity://editor/prefab-stage", "mcpforunity://scene/cameras",
    "mcpforunity://menu-items", "mcpforunity://scene/gameobject-api", "mcpforunity://prefab-api",
}
RESOURCE_PATTERN = r"mcpforunity://scene/gameobject/-?\d+(?:/components|/component/[A-Za-z_][A-Za-z0-9_.]*)?"


def allowed_resource(uri):
    return isinstance(uri, str) and (uri in RESOURCES or re.fullmatch(RESOURCE_PATTERN, uri) is not None)


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
        self.mode = "read-only"  # Legacy full-control settings cannot enable writes.
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
                            "clientInfo": {"name": "unity-controller", "version": "0.2.1"}})
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
        if tool not in READ:
            raise ValueError("Tool is not permitted by the configured access mode")
        if arguments.get("generate_preview") not in (None, False) or arguments.get("generatePreview") not in (None, False):
            raise ValueError("Preview generation is disabled")
        if tool == "manage_asset":
            arguments["generate_preview"] = False
        actions = READ[tool]
        if actions is not None and arguments.get("action") not in actions:
            raise ValueError("An explicitly allowed read action is required")


def text_result(value):
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}


def tool(name, description, properties=None, required=None):
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}


TOOLS = [
    tool("unity_controller_instances", "List connected Unity project names and exact Name@hash identifiers without selecting a project."),
    tool("unity_controller_status", "Read the connection status and the configured Unity Editor instance."),
    tool("unity_controller_catalog", "List permitted Unity operations and their argument schemas. Only explicitly permitted read actions are available."),
    tool("unity_controller_read", "Read editor, project, camera or object/component information from the configured Unity instance.",
         {"uri": {"type": "string", "description": "Use a URI from the catalog, including scene/gameobject/{id} and its components."}}, ["uri"]),
    tool("unity_controller_call", "Invoke a permitted Unity operation on the configured instance. Only read operations are permitted; mutations and code execution are rejected.",
         {"tool": {"type": "string"}, "arguments": {"type": "object"}}, ["tool", "arguments"]),
]


def call(name, args):
    schema = next((t["inputSchema"] for t in TOOLS if t["name"] == name), None)
    if schema is None or not isinstance(args, dict) or set(args) - set(schema["properties"]) or set(schema["required"]) - set(args):
        raise ValueError("Unknown tool or invalid arguments")
    discovery = name == "unity_controller_instances"
    client = Unity(discovery=discovery)
    # Validate locally before establishing any network connection.
    if name == "unity_controller_call":
        client.check(args["tool"], args["arguments"])
    if name == "unity_controller_read" and not allowed_resource(args["uri"]):
        raise ValueError("Resource is not permitted")
    try:
        if discovery:
            return text_result({"instances": client.connect(discovery=True)})
        client.connect()
        if name == "unity_controller_status":
            return text_result({"connected": True, "instance": client.instance, "mode": client.mode,
                                "server": client.info.get("serverInfo")})
        if name == "unity_controller_catalog":
            result, permitted, cursor = {}, [], None
            for _ in range(16):
                result = client.rpc("tools/list", {"cursor": cursor} if cursor else {})
                for t in result.get("tools", []):
                    n = t.get("name")
                    if n in READ:
                        # Return schemas as data, never register unreviewed upstream tools.
                        schema = t.get("inputSchema", {})
                        if READ[n]:
                            schema.setdefault("properties", {})["action"] = {"type": "string", "enum": sorted(READ[n])}
                            schema["required"] = sorted(set(schema.get("required", [])) | {"action"})
                        permitted.append({"name": n, "inputSchema": schema,
                                          "allowed_actions": sorted(READ[n]) if READ[n] else None})
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
                          "serverInfo": {"name": "unity-controller", "version": "0.2.1"}}
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
            print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}, ensure_ascii=False), flush=True)
        except Exception:
            print(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32600, "message": "Invalid request"}}), flush=True)


if __name__ == "__main__":
    main()
