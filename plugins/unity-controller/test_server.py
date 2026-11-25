import os
import unittest
from unittest.mock import patch
import server


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"UNITY_CONTROLLER_INSTANCE": "FoodHunt@123abc",
            "UNITY_CONTROLLER_MODE": "read-only", "UNITY_CONTROLLER_URL": "http://127.0.0.1:8083/mcp"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_denied_calls_never_connect(self):
        with patch.object(server.Unity, "connect") as connect:
            for name, arguments in [("execute_code", {}), ("batch_execute", {}),
                ("set_active_instance", {"instance": "Other@abc"}),
                ("unity_docs", {"action": "lookup"}), ("read_console", {}),
                ("manage_packages", {"action": "search_packages"}),
                ("find_gameobjects", {"unity_instance": "Other@abc"}),
                ("manage_tools", {})]:
                with self.subTest(name=name, arguments=arguments), self.assertRaises(ValueError):
                    server.call("unity_controller_call", {"tool": name, "arguments": arguments})
            connect.assert_not_called()

    def test_read_actions(self):
        c = server.Unity()
        c.check("manage_scene", {"action": "get_hierarchy"})
        c.check("read_console", {"action": "get"})
        c.check("find_gameobjects", {"search_term": "Camera"})

    def test_full_control_still_cannot_change_instance_or_forward_batches(self):
        os.environ["UNITY_CONTROLLER_MODE"] = "full-control"
        c = server.Unity()
        with self.assertRaises(ValueError):
            c.check("execute_code", {"code": "return 1;"})
        for tool in ("batch_execute", "set_active_instance", "execute_custom_tool", "manage_tools"):
            with self.assertRaises(ValueError):
                c.check(tool, {})
        with self.assertRaises(ValueError):
            c.check("execute_code", {"instance": "Other@abc"})

    def test_missing_instance_never_selects_another(self):
        c = server.Unity()
        replies = [{}, {}, {"contents": [{"text": '{"instances":[{"id":"Other@123abc"}]}'}]}]
        with patch.object(c, "rpc", side_effect=replies) as rpc:
            with self.assertRaises(ValueError):
                c.connect()
            self.assertEqual(rpc.call_count, 3)

    def test_remote_plain_http_and_embedded_credentials_rejected(self):
        for url in ("http://192.168.1.5:8083/mcp", "https://user:secret@server/mcp", "https://server/mcp?token=secret"):
            os.environ["UNITY_CONTROLLER_URL"] = url
            with self.assertRaises(ValueError):
                server.Unity()

    def test_unknown_resources_and_arguments_fail_closed(self):
        with patch.object(server.Unity, "connect") as connect:
            for args in ({"uri": "file:///etc/passwd"}, {"uri": "mcpforunity://editor/state", "instance": "Other@abc"}):
                with self.assertRaises(ValueError):
                    server.call("unity_controller_read", args)
            connect.assert_not_called()

    def test_all_allowlisted_actions_and_unknown_writes(self):
        c = server.Unity()
        for tool, actions in server.READ.items():
            for action in actions or [None]:
                c.check(tool, {"action": action} if action else {})
            if actions:
                for action in (None, "execute", "new_upstream_action"):
                    with self.subTest(tool=tool, action=action), self.assertRaises(ValueError):
                        c.check(tool, {"action": action})

    def test_write_side_effect_entrypoints_rejected(self):
        c = server.Unity()
        for tool, action in (("manage_packages", "list_packages"), ("execute_menu_item", None),
                             ("manage_editor", "play"), ("manage_packages", "add_package"),
                             ("manage_profiler", "memory_take_snapshot"), ("manage_physics", "simulate_step"),
                             ("run_tests", None), ("refresh_unity", None)):
            with self.subTest(tool=tool), self.assertRaises(ValueError):
                c.check(tool, {"action": action})
        for value in (True, "true"):
            with self.assertRaises(ValueError):
                c.check("manage_asset", {"action": "search", "generate_preview": value})

    def test_resource_templates(self):
        self.assertTrue(server.allowed_resource("mcpforunity://scene/gameobject/-120/components"))
        for uri in ("mcpforunity://scene/gameobject/1/../../other", "mcpforunity://scene/gameobject/1?instance=other", "file:///secret"):
            self.assertFalse(server.allowed_resource(uri))

    def test_discovery_does_not_select_or_reveal_endpoint(self):
        os.environ["UNITY_CONTROLLER_INSTANCE"] = ""
        with self.assertRaises(ValueError):
            server.Unity()
        c = server.Unity(discovery=True)
        replies = [{}, {}, {"contents": [{"text": '{"instances":[{"id":"FoodHunt@abc","name":"FoodHunt","session_id":"hidden"}]}'}]}]
        with patch.object(c, "rpc", side_effect=replies) as rpc:
            result = c.connect(discovery=True)
            self.assertEqual(result[0]["id"], "FoodHunt@abc")
            self.assertNotIn("session_id", result[0])
            self.assertEqual(rpc.call_count, 3)

    def test_project_edit_and_repair_are_permitted(self):
        c = server.Unity()
        for tool, args in [
            ("manage_scene", {"action":"validate","auto_repair":True}),
            ("manage_physics", {"action":"assign_physics_material","material_path":"Assets/Bounce.physicMaterial"}),
            ("manage_gameobject", {"action":"modify","target":"Cube","position":[1,0,0]}),
            ("manage_asset", {"action":"move","path":"Assets/old.mat","destination":"Assets/new.mat"}),
            ("manage_components", {"action":"set_property","component_type":"Light","property":"intensity","value":2}),
        ]:
            c.check(tool,args)
        a = {"action":"screenshot"}
        c.check("manage_camera",a)
        self.assertEqual(a["output_folder"],"Assets/Screenshots")
        with patch.object(server.Unity, "connect") as connect:
            for t,a in [
                ("execute_code",{}),("blender_bridge",{}),("execute_custom_tool",{}),
                ("generate_model",{}),("generate_audio",{}),("generate_image",{}),("import_model",{}),
                ("create_script",{}),("manage_asset",{"action":"delete","path":"Assets/Editor/code.cs"}),
                ("manage_asset",{"action":"move","path":"Assets/a.mat","destination":"Assets/code.cs"}),
                ("manage_components",{"action":"add","component_type":"CustomBehaviour"}),
                ("manage_material",{"action":"create","material_path":"Assets/../outside.mat"}),
                ("manage_camera",{"action":"screenshot","output_folder":"D:/other"}),
                ("get_sha",{"uri":"mcpforunity://path/Assets/%2e%2e/outside.cs"}),
                ("manage_script",{"action":"read","path":"../other","name":"Example"}),
                ("manage_build",{"action":"platform","target":"Android"}),
                ("unity_docs",{"action":"get_doc"}),("manage_packages",{"action":"list_packages"}),
            ]:
                with self.subTest(tool=t), self.assertRaises(ValueError):
                    server.call("unity_controller_call",{"tool":t,"arguments":a})
            connect.assert_not_called()

    def test_batch_rejects_entire_request_before_connection(self):
        good = {"tool": "manage_scene", "arguments": {"action": "get_active"}}
        bad = {"tool": "manage_packages", "arguments": {"action": "search_packages"}}
        nested = {"tool": "batch_execute", "arguments": {"commands": [good]}}
        with patch.object(server.Unity, "connect") as connect:
            for calls in ([good, bad], [good, nested], [], [good] * 21):
                with self.assertRaises(ValueError):
                    server.call("unity_controller_batch", {"calls": calls})
            connect.assert_not_called()

    def test_batch_forwards_only_checked_queries_and_stops_on_error(self):
        calls = [{"tool": "manage_scene", "arguments": {"action": "validate"}},
                 {"tool": "manage_material", "arguments": {"action": "ping"}}]
        with patch.object(server.Unity, "connect"), patch.object(server.Unity, "close"), patch.object(server.Unity, "rpc", return_value={"isError": True}) as rpc:
            server.call("unity_controller_batch", {"calls": calls})
            self.assertEqual(rpc.call_count, 1)
            self.assertNotIn("auto_repair", rpc.call_args.args[1]["arguments"])

    def test_new_resources_are_exact_allowlist_entries(self):
        for uri in ("mcpforunity://rendering/stats", "mcpforunity://scene/volumes", "mcpforunity://tool-groups", "mcpforunity://custom-tools", "mcpforunity://pipeline/renderer-features"):
            self.assertTrue(server.allowed_resource(uri))
            self.assertFalse(server.allowed_resource(uri + "?action=write"))


class DescriptionTests(unittest.TestCase):
    def test_page_lists_every_exposed_operation(self):
        from pathlib import Path
        page = (Path(__file__).parent / "view/index.html").read_text(encoding="utf-8")
        for tool, actions in server.ALLOWED.items():
            row = next(row for row in page.split("</tr>") if "<code>"+tool+"</code>" in row)
            for action in actions or []:
                self.assertIn(action, row)
        for uri in server.RESOURCES:
            self.assertIn(uri, page)

if __name__ == "__main__":
    unittest.main()
