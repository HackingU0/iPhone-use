import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "claude"), str(ROOT / "workbuddy/tests")]
# Importing the server and the staged handshakes must never send production usage events.
os.environ["IPHONE_USE_ANALYTICS"] = "0"
# The WorkBuddy tests' stand-ins (an upstream module of one's own, a USB stream without a phone) serve here too.
import test_workbuddy as workbuddy_tests
import claude_text
import claude_server


def claude_installer():
    spec = importlib.util.spec_from_file_location("claude_install", ROOT / "claude/install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = claude_installer()
# Tools only another host has. The skills may still name the other ports: they share the phone's state.
OTHER_TOOLS = workbuddy_tests.CODEX_TOOLS + ("AskUserQuestion", "interaction.ask", "mcp__iphone_use__")
OTHER_HOSTS = OTHER_TOOLS + ("Codex", "WorkBuddy", "Doubao")


class TextTests(unittest.TestCase):
    def test_every_rewrite_still_matches_upstream(self):
        claude_server.adapt(workbuddy_tests.pristine_server())
        for relative in claude_text.SKILLS:
            claude_text.skill_text(relative, (ROOT / relative).read_text())
        claude_text.screen_html((ROOT / installer.shared.SCREEN_PAGE).read_text())

    def test_server_speaks_of_claude_and_keeps_the_tool_contract(self):
        upstream = workbuddy_tests.pristine_server()
        tools = copy.deepcopy(upstream.TOOLS)
        claude_server.adapt(upstream)
        described = upstream.INSTRUCTIONS + "".join(tool["description"] for tool in upstream.TOOLS)
        self.assertIn("in the Claude chat", described)
        self.assertIn("no direct Runtime fallback here", upstream.INSTRUCTIONS)
        for word in OTHER_HOSTS + ("view_image", "functions.exec"):
            self.assertNotIn(word, described)
        # Names, schemas and annotations are what the model calls; _meta is for the host.
        for before, after in zip(tools, upstream.TOOLS):
            self.assertEqual({k: v for k, v in before.items() if k not in ("description", "_meta")},
                             {k: v for k, v in after.items() if k not in ("description", "_meta")})

    def test_only_pua_screen_opens_the_view_and_no_loopback_origin_is_asked_for(self):
        upstream = workbuddy_tests.pristine_server()
        claude_server.adapt(upstream)
        views = {tool["name"]: tool["_meta"]["ui"]["resourceUri"] for tool in upstream.TOOLS if tool.get("_meta", {}).get("ui", {}).get("resourceUri")}
        self.assertEqual(views, {"pua_screen": upstream.SCREEN_URI})
        self.assertRegex(upstream.SCREEN_URI, r"^ui://iphone-use/phone-[\d.]+-claude-[0-9a-f]{8}\.html$")
        screen = next(tool for tool in upstream.TOOLS if tool["name"] == "pua_screen")
        self.assertEqual(screen["_meta"]["ui/resourceUri"], upstream.SCREEN_URI)
        self.assertEqual(upstream.SCREEN_META["ui"]["csp"]["connectDomains"], [])
        # The toolbar's own calls stay visible to the view only.
        app_only = {tool["name"] for tool in upstream.TOOLS if tool.get("_meta", {}).get("ui", {}).get("visibility") == ["app"]}
        self.assertIn("pua_screen_frame", app_only)

    def test_phone_is_asked_for_thirty_half_size_frames_and_its_service_outlives_the_server(self):
        upstream = workbuddy_tests.pristine_server()
        claude_server.adapt(upstream)
        settings = sys.modules[upstream.WDAClient.__module__].SESSION_SETTINGS
        self.assertEqual((settings["mjpegServerFramerate"], settings["mjpegScalingFactor"]), (30, 50))
        self.assertIsInstance(sys.modules[upstream.SetupManager.__module__].subprocess, claude_server.doubao.workbuddy.WorkerSubprocess)

    def test_page_is_doubao_works_with_the_toolbar_kept(self):
        upstream = (ROOT / installer.shared.SCREEN_PAGE).read_text()
        page = claude_text.screen_html(upstream)
        self.assertIn(claude_text.SCREEN_SCRIPT, page)
        self.assertIn("app.callServerTool(call, options)", claude_text.SCREEN_SCRIPT)
        for gone in ("readServerResource", "#toolbar"):
            self.assertNotIn(gone, claude_text.SCREEN_SCRIPT)

    def test_skills_name_no_other_hosts_tools_nor_send_the_model_to_a_mac_shell(self):
        for path in (ROOT / "skills").rglob("*.md"):
            relative = path.relative_to(ROOT).as_posix()
            text = claude_text.skill_text(relative, path.read_text())
            for word in OTHER_TOOLS:
                self.assertNotIn(word, text, relative)
        fallback = claude_text.skill_text("skills/iphone-use/references/tool-fallback.md",
                                          (ROOT / "skills/iphone-use/references/tool-fallback.md").read_text())
        self.assertIn("在 Claude 对话里下面两种代码入口都不可用", fallback)
        skill = claude_text.skill_text("skills/iphone-use/SKILL.md", (ROOT / "skills/iphone-use/SKILL.md").read_text())
        self.assertRegex(skill, r"\A---\nname: iphone-use\ndescription: 用户要在手机 / iPhone 上")
        self.assertIn("## 在 Claude 桌面端中使用", skill)

    def test_a_list_out_of_step_with_workbuddys_is_reported(self):
        with self.assertRaises(claude_text.Drift):
            claude_text.retell(claude_text.base.INSTRUCTIONS, ["one text for three passages"], "INSTRUCTIONS")


class Host:
    """One server kept for the whole test, as Claude Desktop keeps one while it runs."""

    def __init__(self, case, env):
        self.child = subprocess.Popen([sys.executable, str(ROOT / installer.ENTRY)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True, env=env)
        case.addCleanup(self.close)
        self.ident = 0
        self.ask("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "claude-ai", "version": "0"}})

    def ask(self, method, params=None):
        self.ident += 1
        self.child.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.ident, "method": method, "params": params or {}}) + "\n")
        self.child.stdin.flush()
        return json.loads(self.child.stdout.readline())

    def frame(self, after_seq=0, **more):
        return self.ask("tools/call", {"name": "pua_screen_frame", "arguments": {"after_seq": after_seq, "last_event_id": 0, **more}})

    def close(self):
        if self.child.poll() is None:
            self.child.stdin.close()
            self.child.wait(timeout=10)
        self.child.stdout.close()


class HostTests(unittest.TestCase):
    """The server as Claude Desktop runs it, with a stand-in for the phone's USB screen stream."""

    def setUp(self):
        self.state = Path(tempfile.mkdtemp(prefix="pua", dir="/tmp"))
        self.addCleanup(shutil.rmtree, self.state, ignore_errors=True)
        (self.state / "config.json").write_text(json.dumps({"udid": "00000000-TESTPHONE0000001"}))
        (self.state / "runtime/forward/node_modules/appium-ios-device").mkdir(parents=True)
        tools = self.state / "bin"
        tools.mkdir()
        (tools / "node").write_text(workbuddy_tests.FAKE_NODE)
        (tools / "node").chmod(0o755)
        self.env = {"PATH": os.pathsep.join([str(tools), *installer.shared.SYSTEM_PATH]), "HOME": str(Path.home()),
                    "IPHONE_USE_STATE_DIR": str(self.state), "IPHONE_USE_ANALYTICS": "0"}

    def test_view_is_handed_the_frames_between_two_polls_and_the_view_page_is_claudes(self):
        host = Host(self, self.env)
        listed = [resource["uri"] for resource in host.ask("resources/list")["result"]["resources"]]
        opens = [tool["_meta"]["ui"]["resourceUri"] for tool in host.ask("tools/list")["result"]["tools"] if tool.get("_meta", {}).get("ui", {}).get("resourceUri")]
        self.assertEqual(listed, opens)
        self.assertRegex(listed[0], r"-claude-[0-9a-f]{8}\.html$")
        page = host.ask("resources/read", {"uri": listed[0]})["result"]["contents"][0]
        self.assertEqual(page["mimeType"], "text/html;profile=mcp-app")
        screen = next(tool for tool in host.ask("tools/list")["result"]["tools"] if tool["name"] == "pua_screen")
        self.assertEqual(screen["_meta"]["ui/resourceUri"], listed[0])
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            frame = host.frame()["result"]["structuredContent"]["frame"]
            if frame:
                break
            time.sleep(0.2)
        else:
            self.fail("no frame arrived")
        time.sleep(0.4)
        shown = host.frame(frame["seq"])["result"]["structuredContent"]
        played = shown["more"] + [shown["frame"]]
        self.assertGreater(len(played), 4)
        self.assertEqual([each["seq"] for each in played], list(range(played[0]["seq"], played[-1]["seq"] + 1)))
        self.assertNotIn("direct", shown)
        self.assertFalse(list(self.state.glob("**/preview.sock")))

    def test_requests_are_traced_into_claudes_own_directory(self):
        (self.state / "claude").mkdir()
        (self.state / "claude/trace").touch()
        host = Host(self, self.env)
        host.ask("tools/call", {"name": "pua_screen", "arguments": {"action": "SECRET-ARGUMENT"}})
        host.close()
        log = (self.state / "claude/host.log").read_text()
        noted = [line["what"] for line in map(json.loads, log.splitlines())]
        self.assertEqual(noted, ["start", "initialize", "tools/call", "stdin closed"])
        self.assertNotIn("SECRET-ARGUMENT", log)
        self.assertFalse((self.state / "doubao").exists())


class InstallTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="claude install ")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.install_dir = self.root / "iphone-use-claude"
        (self.root / "Claude").mkdir()
        self.config = self.root / "Claude/claude_desktop_config.json"

    def install(self, **options):
        return installer.install(self.install_dir, self.config, sys.executable, **options)

    def test_install_registers_a_server_that_starts_under_claudes_environment(self):
        self.config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "preferences": {"theme": "dark"}}))
        result = self.install()
        manifest = json.loads((ROOT / "plugin.json").read_text())
        self.assertEqual((result["version"], result["tools"]), (manifest["version"], 20))
        config = json.loads(self.config.read_text())
        # Other servers and settings stay; one backup of what was there.
        self.assertEqual((config["mcpServers"]["other"], config["preferences"]), ({"command": "x"}, {"theme": "dark"}))
        self.assertEqual(len(list(self.config.parent.glob("claude_desktop_config.json.bak-*"))), 1)
        entry = config["mcpServers"]["iphone_use"]
        self.assertEqual((entry["command"], entry["args"]), (sys.executable, [str(self.install_dir / "claude/claude_server.py")]))
        self.assertTrue(set(installer.shared.SYSTEM_PATH) <= set(entry["env"]["PATH"].split(os.pathsep)))
        self.assertEqual((entry["env"]["NO_PROXY"], entry["env"]["IPHONE_USE_ANALYTICS"]), ("127.0.0.1,localhost,::1", "0"))
        self.assertEqual(installer.shared.handshake(entry), (manifest["version"], 20))
        # A second run with nothing new leaves the file alone.
        self.assertFalse(self.install()["config_changed"])

    def test_analytics_stays_on_only_when_asked(self):
        self.assertNotIn("IPHONE_USE_ANALYTICS", installer.server_entry(self.install_dir, sys.executable, analytics=True)["env"])

    def test_skill_archives_hold_the_skill_folder_worded_for_claude(self):
        result = self.install()
        for name in ("server/iphone_use.py", "tooling/forward.mjs", "assets/phone-screen.html", "workbuddy/mcp_server.py",
                     "doubao/mcp_stdio.py", "doubao/doubao_text.py", "claude/claude_text.py", installer.MARKER):
            self.assertTrue((self.install_dir / name).is_file(), name)
        for name in installer.shared.CODEX_ONLY + ("claude/install.py", "doubao/install.py", "workbuddy/install.py", "tests"):
            self.assertFalse((self.install_dir / name).exists(), name)
        self.assertEqual(result["skills"], [str(self.install_dir / "skill-uploads" / f"{name}.zip") for name in installer.SKILLS])
        for name, path in zip(installer.SKILLS, map(Path, result["skills"])):
            with zipfile.ZipFile(path) as bundle:
                names = bundle.namelist()
                self.assertTrue(all(entry.startswith(name + "/") for entry in names), names)
                skill = bundle.read(f"{name}/SKILL.md").decode()
            self.assertEqual(sorted(names), sorted(f"{name}/" + p.relative_to(self.install_dir / "skills" / name).as_posix()
                                                   for p in (self.install_dir / "skills" / name).rglob("*") if p.is_file()))
            # What Claude's upload asks of a skill: a matching name and a description within 1024 characters.
            found = re.match(r"\A---\nname: (\S+)\ndescription: (.+)\n", skill)
            self.assertEqual(found.group(1), name)
            self.assertLessEqual(len(found.group(2)), 1024)
            self.assertIn("## 在 Claude 桌面端中使用", skill)

    def test_a_server_or_directory_of_someone_elses_is_left_alone(self):
        self.config.write_text(json.dumps({"mcpServers": {"iphone_use": {"command": "python3", "args": ["/elsewhere/server/iphone_use.py"]}}}))
        with self.assertRaisesRegex(installer.InstallError, "/elsewhere/server/iphone_use.py"):
            self.install()
        self.assertFalse(self.install_dir.exists())
        self.install(force=True)
        (self.install_dir / installer.MARKER).unlink()
        with self.assertRaises(installer.InstallError):
            self.install()

    def test_a_missing_claude_directory_or_broken_config_changes_nothing(self):
        with self.assertRaises(installer.InstallError):
            installer.install(self.install_dir, self.root / "missing/claude_desktop_config.json", sys.executable)
        self.config.write_text("{not json")
        with self.assertRaises(installer.InstallError):
            self.install()
        self.assertEqual(self.config.read_text(), "{not json")
        self.assertFalse(self.install_dir.exists())

    def test_uninstall_removes_the_entry_and_the_server_and_keeps_the_rest(self):
        self.assertEqual(installer.uninstall(self.install_dir, self.config), [])
        self.config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
        self.install()
        removed = installer.uninstall(self.install_dir, self.config)
        self.assertEqual(len(removed), 2)
        self.assertFalse(self.install_dir.exists())
        self.assertEqual(json.loads(self.config.read_text()), {"mcpServers": {"other": {"command": "x"}}})


if __name__ == "__main__":
    unittest.main()
