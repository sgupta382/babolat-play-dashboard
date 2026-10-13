import unittest
from datetime import datetime
from pathlib import Path

from babolat_play.parser import HEADER_LEN, REC_LEN, FormatError, parse_log

FIX = Path(__file__).parent / "fixtures"
# Start record after a clock reset: 2012-09-01 23:19:40, 427 s long, 2 records.
START = bytes([0, 23, 19, 40, 1, 9, 12, 171, 1, 2, 0, 1, 0])


class ParserTest(unittest.TestCase):
    def test_real_session(self):
        [s] = parse_log((FIX / "LOG000.BIN").read_bytes(), "LOG000.BIN")
        self.assertEqual(s.started_at, datetime(2022, 8, 29, 19, 17, 33))
        self.assertEqual(len(s.swings), 151)
        counts = {k: sum(w.stroke == k for w in s.swings) for k in ("forehand", "backhand", "serve", "volley")}
        self.assertEqual(counts, {"forehand": 38, "backhand": 26, "serve": 43, "volley": 44})
        self.assertEqual(sum(w.glitch for w in s.swings), 1)
        self.assertEqual(max(w.speed_kmh for w in s.swings if w.stroke == "serve"), 133)
        self.assertEqual(s.duration_s, 4168)
        self.assertFalse(s.clock_reset)

    def test_factory_log(self):
        [s] = parse_log((FIX / "LOG001.BIN").read_bytes())
        self.assertEqual(s.started_at, datetime(2012, 9, 1, 15, 29, 52))
        self.assertEqual(len(s.swings), 3)
        self.assertTrue(s.clock_reset)

    def test_markers_are_not_swings(self):
        marker = bytes([10, 1, 3, 0, 97, 0, 0, 0, 0, 0, 0, 150, 0])
        swing = bytes([3, 6, 1, 60, 30, 0, 0, 236, 6, 0, 0, 159, 0])
        [s] = parse_log(bytes(HEADER_LEN) + START + marker + swing)
        self.assertEqual([w.stroke for w in s.swings], ["forehand"])
        self.assertEqual(s.duration_s, 427)

    def test_slow_flat_or_slice_groundstroke_is_a_volley(self):
        def stroke(code, spin, mph):
            rec = bytes([code, 6, spin, 40, mph, 0, 0, 0, 0, 0, 0, 5, 0])
            return parse_log(bytes(HEADER_LEN) + START + rec)[0].swings[0].stroke
        self.assertEqual(stroke(3, 0, 10), "volley")       # slow flat forehand
        self.assertEqual(stroke(4, 2, 19), "volley")       # slow slice backhand
        self.assertEqual(stroke(3, 1, 10), "forehand")     # slow topspin: groundstroke
        self.assertEqual(stroke(4, 2, 20), "backhand")     # at the threshold: groundstroke
        self.assertEqual(stroke(2, 0, 10), "serve")        # serves are never volleys

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
