import os
import json
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
        c.check("manage_camera", {"action": "list_cameras"})
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
                args = {"action": action} if action else {}
                if tool == "manage_asset" and action == "get_info":
                    args["path"] = "Assets/Example.mat"
                c.check(tool, args)
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
        self.assertTrue(server.allowed_resource("mcpforunity://scene/gameobject/-120"))
        self.assertFalse(server.allowed_resource("mcpforunity://scene/gameobject/-120/components"))
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
            self.assertEqual(result, [{"id":"abc"}])
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
        for uri in server.RESOURCES:
            self.assertTrue(server.allowed_resource(uri))
            self.assertFalse(server.allowed_resource(uri + "?action=write"))
        for uri in ("editor/windows", "custom-tools", "menu-items", "project/info", "tool-groups"):
            self.assertFalse(server.allowed_resource("mcpforunity://" + uri))

    def test_private_sources_rejected_before_contact(self):
        denied = [
            ("manage_packages", {"action": "list_registries"}), ("read_console", {"action":"get"}),
            ("manage_script", {"action":"read"}), ("find_in_file", {"uri":"Assets/File.cs"}),
            ("manage_ui", {"action":"read"}), ("manage_asset", {"action":"get_info","path":"Assets/notes.pdf"}),
            ("manage_asset", {"action":"search","filter_type":"TextAsset"}),
            ("manage_camera", {"action":"set_body", "properties":{"bodyType":"CustomComponent"}}),
            ("manage_graphics", {"action":"volume_create_profile","path":"Assets/script.cs"}),
            ("manage_animation", {"action":"clip_create","properties":{"clipPath":"Assets/Test.anim"}}),
            ("manage_profiler", {"action":"profiler_status","search_path":"other"}),
            ("manage_ui", {"action":"update_panel_settings","path":"Assets/p.asset","settings":{"themeStyleSheet":"other"}}),
        ]
        with patch.object(server.Unity,"rpc") as rpc:
            for t,a in denied:
                with self.subTest(t=t,a=a), self.assertRaises(ValueError):
                    server.call("unity_controller_batch",{"calls":[{"tool":t,"arguments":a}]})
            rpc.assert_not_called()

    def test_new_project_edits(self):
        c=server.Unity()
        for t,a in [
            ("manage_animation",{"action":"clip_create","clip_path":"Assets/A.anim"}),
            ("manage_animation",{"action":"clip_set_curve","clip_path":"Assets/A.anim","properties":{"type":"Transform","propertyPath":"localScale.x","keys":[{"time":0,"value":1}]}}),
            ("manage_ui",{"action":"create_panel_settings","path":"Assets/Panel.asset"}),
            ("manage_physics",{"action":"create_physics_material","name":"Ice","path":"Assets/Physics"}),
            ("manage_graphics",{"action":"volume_create_profile","path":"Assets/Volume.asset"}),
            ("manage_camera",{"action":"add_extension","properties":{"extensionType":"CinemachineConfiner2D"}}),
        ]:
            with self.subTest(t=t): c.check(t,a)

    def test_output_privacy_all_relay_paths(self):
        marker = "internal.example.test"
        payload = {"success":True, "message":marker, "data":{"name":marker,"path":marker,
                   "rootCount":4,"items":[{"id":2,"name":marker,marker:7,"properties":{"ip":marker}}]}}
        text = json.dumps(payload)
        raw = {"structuredContent":payload, "_meta":{"host":marker},
               "content":[{"type":"text","text":text},{"type":"image","data":marker}],
               "contents":[{"text":text, "uri":marker}]}
        for raw_result in (raw,{k:v for k,v in raw.items() if k != "structuredContent"}):
            with patch.object(server.Unity,"connect"), patch.object(server.Unity,"rpc",return_value=raw_result):
                args={"tool":"manage_scene","arguments":{"action":"get_active"}}
                for method,params in (("unity_controller_call",args),("unity_controller_batch",{"calls":[args]}),
                                      ("unity_controller_read",{"uri":"mcpforunity://scene/cameras"})):
                    result=server.call(method,params)
                    self.assertNotIn(marker,json.dumps(result))
                    self.assertIn("rootCount",json.dumps(result))
        self.assertNotIn(marker,json.dumps(server.project_reply({"isError":True,"content":[{"text":marker}]})))

    def test_catalog_uses_packaged_schemas(self):
        upstream={"tools":[{"name":"manage_asset","inputSchema":{"description":"secret-host.example"}}]}
        with patch.object(server.Unity,"connect"),patch.object(server.Unity,"rpc",return_value=upstream):
            catalog=server.call("unity_controller_catalog",{})
        self.assertNotIn("secret-host",json.dumps(catalog))
        self.assertIn("filter_type",json.dumps(catalog))



class MenuReviewTests(unittest.TestCase):
    def setUp(self):
        settings = patch.dict(os.environ, {"UNITY_CONTROLLER_INSTANCE": "Example@abc"})
        settings.start()
        self.addCleanup(settings.stop)
        self.path = "Tools/Example/Custom Export"
        self.args = {"menu_path": self.path}

    def test_each_dispatch_needs_its_own_decision(self):
        reply = {"structuredContent":{"success":True,"message":"private-host"}}
        with patch("server.menu_review.ask_once", side_effect=[True, False, True]) as review, \
             patch.object(server.Unity,"connect") as connect, patch.object(server.Unity,"rpc",return_value=reply) as rpc:
            for expected in (True, False, True):
                result = server.call(server.MENU_TOOL, self.args)
                self.assertEqual(not result.get("isError",False), expected)
                self.assertNotIn("private-host",json.dumps(result))
            self.assertEqual(review.call_count,3)
            for args in review.call_args_list:
                self.assertEqual(args.args[:2],("Example@abc",self.path))
            self.assertEqual(connect.call_count,2)
            self.assertEqual(rpc.call_count,2)
            self.assertEqual(rpc.call_args.args,("tools/call",{"name":"execute_menu_item","arguments":self.args}))

    def test_known_prohibited_paths_and_raw_routes(self):
        with patch("server.menu_review.ask_once") as review, patch.object(server.Unity,"rpc") as rpc:
            for path in ("Help/Manual", "Tools/Blender/Export", "Tools/Open Documentation", "Assets/Open",
                         "Tools/文档/打开", "Tools/Test\nExport", "Tools/Test\u202eExport", "Tools//Export", " Tools/Export"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    server.call(server.MENU_TOOL,{"menu_path":path})
            for n in (server.MENU_TOOL,"execute_menu_item"):
                entry={"tool":n,"arguments":self.args}
                for method, args in (("unity_controller_call",entry),("unity_controller_batch",{"calls":[entry]})):
                    with self.assertRaises(ValueError): server.call(method,args)
            for override in ("approved","instance","token"):
                with self.assertRaises(ValueError):server.call(server.MENU_TOOL,{**self.args,override:True})
            review.assert_not_called()
            rpc.assert_not_called()

    def test_cancellation_and_uncertain_dispatch(self):
        from threading import Event
        cancel=Event()
        def decide(*args):
            cancel.set()
            return True
        with patch("server.menu_review.ask_once",side_effect=decide), patch.object(server.Unity,"connect") as connect:
            self.assertTrue(server.call(server.MENU_TOOL,self.args,cancel)["isError"])
            connect.assert_not_called()
        with patch("server.menu_review.ask_once",return_value=True), patch.object(server.Unity,"connect"), \
             patch.object(server.Unity,"rpc",side_effect=TimeoutError("private-host")) as rpc:
            result=server.call(server.MENU_TOOL,self.args)
            self.assertTrue(result["isError"])
            self.assertNotIn("private-host",json.dumps(result))
            rpc.assert_called_once()

    def test_helper_exit_and_timeout_fail_closed(self):
        from threading import Event
        import menu_review
        with patch("menu_review.subprocess.Popen") as factory:
            proc=factory.return_value.__enter__.return_value
            for status, allowed in [(1,False),(0,False),(menu_review.APPROVED,True)]:
                proc.poll.return_value=status
                self.assertEqual(menu_review.ask_once("Example@abc",self.path,Event()),allowed)
            with patch.object(menu_review,"REVIEW_SECONDS",0):
                proc.poll.return_value=None
                self.assertFalse(menu_review.ask_once("Example@abc",self.path,Event()))
                proc.kill.assert_called_once()
        with patch("menu_review.subprocess.Popen",side_effect=OSError):
            self.assertFalse(menu_review.ask_once("Example@abc",self.path,Event()))


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
