import unittest
from pathlib import Path

from babolat_play.parser import REC_LEN, parse_log
from babolat_play.store import Store

FIX = Path(__file__).parent / "fixtures"


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.db = Store(":memory:")
        self.raw = (FIX / "LOG000.BIN").read_bytes()

    def test_new_then_skip(self):
        s = parse_log(self.raw)[0]
        self.assertEqual(self.db.upsert_session(s), "new")
        self.assertEqual(self.db.upsert_session(s), "skipped")
        self.assertEqual(len(self.db.sessions()), 1)

    def test_grown_session_updates(self):
        self.db.upsert_session(parse_log(self.raw[:-2 * REC_LEN])[0])
        self.assertEqual(self.db.upsert_session(parse_log(self.raw)[0]), "updated")
        [s] = self.db.sessions()
        self.assertEqual(len(s.swings), 151)

    def test_roundtrip_fields(self):
        orig = parse_log(self.raw)[0]
        self.db.upsert_session(orig)
        back = self.db.sessions()[0]
        self.assertEqual(back.started_at, orig.started_at)
        self.assertEqual(back.swings, orig.swings)

    def test_import_ids_increase(self):
        self.assertIsNone(self.db.latest_import_id())
        a = self.db.begin_import()
        b = self.db.begin_import()
        self.assertGreater(b, a)
        self.assertEqual(self.db.latest_import_id(), b)


if __name__ == "__main__":
    unittest.main()
