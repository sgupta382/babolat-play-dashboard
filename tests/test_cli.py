import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from babolat_play import agent, cli, demo

FIX = Path(__file__).parent / "fixtures"


class DemoTest(unittest.TestCase):
    def test_synthetic_sessions_deterministic(self):
        a, b = demo.synthetic_sessions(seed=7), demo.synthetic_sessions(seed=7)
        self.assertEqual(len(a), 11)
        self.assertEqual([s.id for s in a], [s.id for s in b])
        self.assertEqual(a[0].swings, b[0].swings)
        self.assertTrue(all(s.source == "synthetic" for s in a))
        self.assertTrue(all(90 <= len(s.swings) <= 200 for s in a))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"BABOLAT_PLAY_HOME": self.home})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.home)

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch("babolat_play.cli.notify") as n:
            code = cli.main(list(args))
        return code, buf.getvalue(), n

    def test_import_then_reimport(self):
        code, out, n = self.run_cli("import", "--path", str(FIX), "--auto")
        self.assertEqual(code, 0)
        self.assertIn("1 new", out)
        n.assert_called_once()
        self.assertTrue((Path(self.home) / "site" / "data.js").exists())
        code, out, n = self.run_cli("import", "--path", str(FIX), "--auto")
        self.assertIn("0 new", out)
        n.assert_not_called()

    def test_auto_without_racket_is_silent(self):
        with mock.patch("babolat_play.cli.find_racket_volumes", return_value=[]):
            code, out, n = self.run_cli("import", "--auto")
        self.assertEqual((code, out), (0, ""))
        n.assert_not_called()

    def test_demo_builds_site(self):
        out_dir = Path(self.home) / "demo-site"
        code, _, _ = self.run_cli("demo", "--out", str(out_dir))
        self.assertEqual(code, 0)
        js = (out_dir / "data.js").read_text()
        self.assertIn("synthetic", js)
        self.assertIn('"is_new":true', js)


class AgentTest(unittest.TestCase):
    def test_plists(self):
        imp, srv = agent.build_plists(Path("/repo"), Path("/home/.babolat-play"), "/usr/bin/python3", 8765)
        self.assertTrue(imp["StartOnMount"])
        self.assertEqual(imp["ProgramArguments"][-2:], ["import", "--auto"])
        self.assertEqual(imp["EnvironmentVariables"]["PYTHONPATH"], "/repo")
        self.assertTrue(srv["KeepAlive"])
        self.assertIn("8765", srv["ProgramArguments"])


if __name__ == "__main__":
    unittest.main()
