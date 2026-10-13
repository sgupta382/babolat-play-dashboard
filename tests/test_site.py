import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from babolat_play import site
from babolat_play.parser import parse_log
from babolat_play.store import Store

FIX = Path(__file__).parent / "fixtures"
PREFIX = "window.PLAY_DATA="


def read_data(out: Path) -> dict:
    js = (out / "data.js").read_text()
    return json.loads(js[len(PREFIX):].rstrip(";\n"))


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = Store(":memory:")
        self.db.upsert_session(parse_log((FIX / "LOG000.BIN").read_bytes())[0])

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_payload(self):
        p = site.build_payload(self.db)
        s = p["sessions"][0]
        self.assertEqual(len(s["swings"]), 151)
        self.assertEqual(s["duration_s"], 3568)
        self.assertEqual(s["started_at"], "2022-08-29T19:17:33")

    def test_build_writes_app_and_data(self):
        out = site.build_site(self.db, self.tmp / "site")
        self.assertTrue((out / "index.html").exists())
        self.assertTrue((out / "data.js").read_text().startswith(PREFIX))
        self.assertEqual(len(read_data(out)["sessions"]), 1)

    def test_rebuild_replaces_data(self):
        out = site.build_site(self.db, self.tmp / "site", demo_label="x")
        site.build_site(self.db, out)
        self.assertIsNone(read_data(out)["demo"])
        self.assertFalse((self.tmp / "site.old").exists())

    def test_failed_build_keeps_previous_site(self):
        out = site.build_site(self.db, self.tmp / "site")
        with mock.patch.object(site, "_write_data", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                site.build_site(self.db, out)
        self.assertTrue((out / "data.js").exists())
        self.assertFalse((self.tmp / "site.tmp").exists())

    def test_new_milestones_flagged(self):
        from babolat_play.milestones import compute_milestones
        self.db.sync_milestones(compute_milestones(self.db.sessions()), self.db.begin_import())
        ms = site.build_payload(self.db)["milestones"]
        self.assertTrue(ms and all(m["is_new"] for m in ms))


if __name__ == "__main__":
    unittest.main()
