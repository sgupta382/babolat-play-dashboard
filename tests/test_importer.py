import shutil
import tempfile
import unittest
from pathlib import Path

from babolat_play.importer import find_racket_volumes, import_path
from babolat_play.parser import REC_LEN
from babolat_play.store import Store

FIX = Path(__file__).parent / "fixtures"


class ImporterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vol = self.tmp / "BABOLAT"
        self.vol.mkdir()
        for f in ("LOG000.BIN", "LOG001.BIN"):
            shutil.copy(FIX / f, self.vol / f)
        (self.vol / "PLAY.URL").write_text("x")
        self.db = Store(":memory:")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_first_import_skips_factory_log(self):
        r = import_path(self.vol, self.db, archive=self.tmp / "raw")
        self.assertEqual((len(r.new), len(r.updated), r.errors), (1, 0, []))
        self.assertEqual(len(list((self.tmp / "raw").glob("*.BIN"))), 2)

    def test_reimport_is_noop(self):
        import_path(self.vol, self.db)
        r = import_path(self.vol, self.db)
        self.assertEqual((len(r.new), len(r.updated)), (0, 0))

    def test_grown_log_updates(self):
        full = (self.vol / "LOG000.BIN").read_bytes()
        (self.vol / "LOG000.BIN").write_bytes(full[:-5 * REC_LEN])
        import_path(self.vol, self.db)
        (self.vol / "LOG000.BIN").write_bytes(full)
        r = import_path(self.vol, self.db)
        self.assertEqual((len(r.new), len(r.updated)), (0, 1))

    def test_corrupt_file_does_not_block_others(self):
        (self.vol / "LOG002.BIN").write_bytes(b"\x00" * 51)
        r = import_path(self.vol, self.db)
        self.assertEqual(len(r.new), 1)
        self.assertTrue(any("LOG002.BIN" in e for e in r.errors))

    def test_volume_untouched(self):
        def snap():
            return {p.name: (p.stat().st_mtime, p.stat().st_size) for p in self.vol.iterdir()}
        before = snap()
        import_path(self.vol, self.db, archive=self.tmp / "raw")
        self.assertEqual(before, snap())

    def test_find_volume(self):
        (self.tmp / "Other").mkdir()
        self.assertEqual(find_racket_volumes([self.tmp]), [self.vol])

    def test_find_volume_missing_root(self):
        self.assertEqual(find_racket_volumes([self.tmp / "nope"]), [])


if __name__ == "__main__":
    unittest.main()
