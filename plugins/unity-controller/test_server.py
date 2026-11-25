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
                ("manage_scene", {"action": "save"}), ("read_console", {}),
                ("read_console", {"action": "clear"}),
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
                for action in (None, "create", "delete", "save", "execute", "new_upstream_action"):
                    with self.subTest(tool=tool, action=action), self.assertRaises(ValueError):
                        c.check(tool, {"action": action})

    def test_write_side_effect_entrypoints_rejected(self):
        c = server.Unity()
        for tool, action in (("manage_camera", "screenshot"), ("manage_ui", "render_ui"),
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


if __name__ == "__main__":
    unittest.main()
