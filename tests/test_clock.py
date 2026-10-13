import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock

from babolat_play import cli, clock, paths
from babolat_play.importer import import_path, redecode
from babolat_play.parser import HEADER_LEN, parse_log
from babolat_play.store import Store

FIX = Path(__file__).parent / "fixtures"


def reset_log(hh, mm, ss, duration_s, swings=12):
    """A log recorded after a clock reset (racket date 2012-09-01)."""
    start = bytes([0, hh, mm, ss, 1, 9, 12, duration_s & 0xFF, duration_s >> 8, swings, 0, 1, 0])
    recs = b"".join(bytes([3, 6, 1, 60, 40, 0, 0, 0, 0, 0, 0, 10 + i, 0]) for i in range(swings))
    return bytes(HEADER_LEN) + start + recs


class ClockTest(unittest.TestCase):
    def setUp(self):
        self.a = parse_log(reset_log(23, 19, 40, 427), "LOG002.BIN")[0]
        self.b = parse_log(reset_log(23, 48, 16, 364), "LOG008.BIN")[0]
        # Last session ended 23:54:20 on the racket and 17:50 in real life.
        self.clk = clock.calibrate([self.a, self.b], datetime(2026, 10, 13, 17, 50))

    def test_offset_from_last_session_end(self):
        self.assertEqual(self.clk.correct(self.b).started_at, datetime(2026, 10, 13, 17, 43, 56))
        self.assertEqual(self.clk.correct(self.a).started_at, datetime(2026, 10, 13, 17, 15, 20))

    def test_sessions_after_calibration_are_dated(self):
        # Racket clock 2012-09-02 10:00, ten hours after the anchor: the next day in real life.
        [later] = parse_log(bytes(HEADER_LEN) + bytes([0, 10, 0, 0, 2, 9, 12, 0, 0, 0, 0, 0, 0]))
        self.assertEqual(self.clk.correct(later).started_at, datetime(2026, 10, 14, 3, 55, 40))

    def test_another_reset_is_not_dated(self):
        after_new_reset = parse_log(reset_log(1, 5, 0, 300))[0]  # earlier than the anchor, unseen
        self.assertIsNone(self.clk.correct(after_new_reset))

    def test_good_clock_untouched(self):
        [s] = parse_log((FIX / "LOG000.BIN").read_bytes())
        self.assertIs(self.clk.correct(s), s)

    def test_no_reset_sessions(self):
        with self.assertRaises(ValueError):
            clock.calibrate(parse_log((FIX / "LOG000.BIN").read_bytes()), datetime(2026, 1, 1))

    def test_save_load_roundtrip(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            clock.save(tmp / "clock.json", self.clk)
            loaded = clock.load(tmp / "clock.json")
            self.assertEqual((loaded.offset_s, loaded.anchor, loaded.ids),
                             (self.clk.offset_s, self.clk.anchor, self.clk.ids))
            self.assertIsNone(clock.load(tmp / "missing.json"))
        finally:
            shutil.rmtree(tmp)


class ResetImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vol = self.tmp / "BABOLAT"
        self.vol.mkdir()
        shutil.copy(FIX / "LOG000.BIN", self.vol / "LOG000.BIN")
        (self.vol / "LOG002.BIN").write_bytes(reset_log(23, 19, 40, 427))
        self.db = Store(":memory:")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_held_back_without_clock(self):
        r = import_path(self.vol, self.db)
        self.assertEqual((len(r.new), r.undated), (1, 1))
        self.assertTrue(all(s.started_at.year != 2012 for s in self.db.sessions()))

    def test_dated_with_clock(self):
        clk = clock.calibrate(parse_log(reset_log(23, 19, 40, 427)), datetime(2026, 10, 13, 17, 30))
        r = import_path(self.vol, self.db, clock=clk)
        self.assertEqual((len(r.new), r.undated), (2, 0))
        self.assertEqual(max(s.started_at for s in self.db.sessions()), datetime(2026, 10, 13, 17, 22, 53))

    def test_redecode_keeps_start_time_and_rewrites_swings(self):
        import_path(self.vol, self.db, archive=self.tmp / "raw")
        sid = self.db.sessions()[0].id
        self.db.db.execute("UPDATE swings SET stroke = 'stale' WHERE session_id = ?", (sid,))
        self.assertEqual(redecode(self.tmp / "raw", self.db), 1)  # the held-back log isn't stored
        [s] = self.db.sessions()
        self.assertEqual(s.started_at, datetime(2022, 8, 29, 19, 17, 33))
        self.assertNotIn("stale", {w.stroke for w in s.swings})


class ClockCliTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"BABOLAT_PLAY_HOME": self.home})
        self.env.start()
        self.vol = Path(self.home) / "BABOLAT"
        self.vol.mkdir()
        (self.vol / "LOG002.BIN").write_bytes(reset_log(23, 19, 40, 427))

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.home)

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch("babolat_play.cli.notify") as n:
            code = cli.main(list(args))
        return code, buf.getvalue(), n

    def test_auto_import_asks_for_clock_then_clock_imports(self):
        code, out, n = self.run_cli("import", "--path", str(self.vol), "--auto")
        self.assertIn("racket clock", out)
        n.assert_called_once()
        code, out, _ = self.run_cli("clock", "2026-10-13 17:30", "--path", str(self.vol))
        self.assertEqual(code, 0)
        self.assertIn("2012-09-01 23:19 -> 2026-10-13 17:22", out)  # 7 min session ending 17:30
        self.assertIn("1 new", out)
        self.assertTrue(paths.clock_path().exists())
