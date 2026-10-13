import unittest
from datetime import datetime
from pathlib import Path

from babolat_play.parser import HEADER_LEN, REC_LEN, FormatError, parse_log

FIX = Path(__file__).parent / "fixtures"


class ParserTest(unittest.TestCase):
    def test_real_session(self):
        [s] = parse_log((FIX / "LOG000.BIN").read_bytes(), "LOG000.BIN")
        self.assertEqual(s.started_at, datetime(2022, 8, 29, 19, 17, 33))
        self.assertEqual(len(s.swings), 151)
        counts = {k: sum(w.stroke == k for w in s.swings) for k in ("forehand", "backhand", "serve", "volley")}
        self.assertEqual(counts, {"forehand": 52, "backhand": 39, "serve": 43, "volley": 17})
        self.assertEqual(sum(w.glitch for w in s.swings), 1)
        self.assertEqual(max(w.speed_kmh for w in s.swings if w.stroke == "serve"), 133)

    def test_factory_log(self):
        [s] = parse_log((FIX / "LOG001.BIN").read_bytes())
        self.assertEqual(s.started_at, datetime(2012, 9, 1, 15, 29, 52))
        self.assertEqual(len(s.swings), 3)

    def test_multi_session_file_splits(self):
        a = (FIX / "LOG000.BIN").read_bytes()
        b = (FIX / "LOG001.BIN").read_bytes()
        sessions = parse_log(a + b[HEADER_LEN:])
        self.assertEqual([len(s.swings) for s in sessions], [151, 3])
        self.assertNotEqual(sessions[0].id, sessions[1].id)

    def test_id_stable_when_log_grows(self):
        a = (FIX / "LOG000.BIN").read_bytes()
        self.assertEqual(parse_log(a[:-REC_LEN])[0].id, parse_log(a)[0].id)

    def test_truncated_file_rejected(self):
        with self.assertRaises(FormatError):
            parse_log((FIX / "LOG000.BIN").read_bytes()[:-3])

    def test_bad_date_rejected(self):
        a = bytearray((FIX / "LOG000.BIN").read_bytes())
        a[HEADER_LEN + 5] = 13  # month 13
        with self.assertRaises(FormatError):
            parse_log(bytes(a))


if __name__ == "__main__":
    unittest.main()
