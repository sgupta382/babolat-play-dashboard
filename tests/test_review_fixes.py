"""Regression tests for findings from the final whole-branch review."""
import io
import json
import os
import plistlib
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from babolat_play import agent, cli, notify

FIX = Path(__file__).parent / "fixtures"


def read_data(site_dir: Path) -> dict:
    js = (site_dir / "data.js").read_text()
    return json.loads(js[len("window.PLAY_DATA="):].rstrip(";\n"))


class NotifyTest(unittest.TestCase):
    def test_non_ascii_reaches_osascript_unescaped(self):  # I1
        with mock.patch.object(notify.sys, "platform", "darwin"), \
                mock.patch.object(notify.subprocess, "run") as run:
            notify.notify("Babolat Play", "1 new · 🏆 record")
        script = run.call_args[0][0][2]
        self.assertIn("🏆", script)
        self.assertNotIn("\\u", script)


class CliHomeTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"BABOLAT_PLAY_HOME": str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.home)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), mock.patch("babolat_play.cli.notify") as n:
            code = cli.main(list(args))
        return code, out.getvalue(), n

    def test_noop_reimport_keeps_new_banner(self):  # I2
        self.run_cli("import", "--path", str(FIX))
        before = read_data(self.home / "site")
        self.run_cli("import", "--path", str(FIX), "--auto")
        after = read_data(self.home / "site")
        self.assertEqual(after["latest_import_id"], before["latest_import_id"])
        self.assertTrue(any(m["is_new"] for m in after["milestones"]))

    def test_unlistable_volume_notifies(self):  # I3
        vol = self.home / "BABOLAT"
        vol.mkdir()
        with mock.patch("babolat_play.cli.find_racket_volumes", return_value=[vol]), \
                mock.patch("babolat_play.importer.os.listdir", side_effect=PermissionError("denied")):
            code, _, n = self.run_cli("import", "--auto")
        self.assertEqual(code, 1)
        n.assert_called_once()


class AgentFixesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.agents = mock.patch.object(agent, "AGENTS_DIR", self.tmp / "LaunchAgents")
        self.agents.start()
        self.lc = mock.patch.object(agent, "_launchctl", return_value=True)
        self.lc.start()

    def tearDown(self):
        self.lc.stop()
        self.agents.stop()
        shutil.rmtree(self.tmp)

    def test_stage_package_copies_code_out_of_clone(self):  # I4
        lib = agent.stage_package(self.tmp / "home")
        self.assertTrue((lib / "babolat_play" / "cli.py").exists())
        self.assertTrue((lib / "babolat_play" / "app" / "index.html").exists())
        agent.stage_package(self.tmp / "home")  # re-staging replaces cleanly
        self.assertTrue((lib / "babolat_play" / "cli.py").exists())

    def test_install_points_agents_at_staged_copy(self):  # I4
        home = self.tmp / "home"
        agent.install(home, "/usr/bin/python3", 8765)
        imp = plistlib.loads((self.tmp / "LaunchAgents" / f"{agent.IMPORT_LABEL}.plist").read_bytes())
        self.assertEqual(imp["EnvironmentVariables"]["PYTHONPATH"], str(home / "lib"))

    def test_no_serve_removes_existing_server_agent(self):  # I7
        home = self.tmp / "home"
        agent.install(home, "/usr/bin/python3", 8765, serve=True)
        agent.install(home, "/usr/bin/python3", 8765, serve=False)
        self.assertFalse((self.tmp / "LaunchAgents" / f"{agent.SERVE_LABEL}.plist").exists())
        self.assertTrue((self.tmp / "LaunchAgents" / f"{agent.IMPORT_LABEL}.plist").exists())


if __name__ == "__main__":
    unittest.main()
