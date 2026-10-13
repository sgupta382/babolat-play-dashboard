import unittest
from datetime import datetime, timedelta

from babolat_play.milestones import compute_milestones
from babolat_play.parser import Session, Swing
from babolat_play.store import Store


def mk(day, serve=100, n_fh=20, top=0.5, fh_speed=40.0):
    sw = [Swing(i, i * 10, "forehand", "topspin" if i < n_fh * top else "flat", 6, fh_speed, False, "")
          for i in range(n_fh)]
    sw.append(Swing(n_fh, n_fh * 10, "serve", "flat", 6, float(serve), False, ""))
    return Session(f"s{day}", datetime(2024, 1, 1) + timedelta(days=day), "t", sw)


def keys(ms):
    return [m.key for m in ms]


class MilestoneTest(unittest.TestCase):
    def test_first_session_no_pb(self):
        ks = keys(compute_milestones([mk(0)]))
        self.assertIn("first_session", ks)
        self.assertIn("sessions_1", ks)
        self.assertFalse(any(k.startswith("pb_") for k in ks))

    def test_serve_pb(self):
        ks = keys(compute_milestones([mk(0, 100), mk(7, 120), mk(14, 110)]))
        self.assertIn("pb_serve@s7", ks)
        self.assertNotIn("pb_serve@s14", ks)

    def test_pb_value_and_order(self):
        ms = compute_milestones([mk(0, 100), mk(7, 120)])
        pb = next(m for m in ms if m.key == "pb_serve@s7")
        self.assertEqual((pb.value, pb.stroke, pb.session_id), (120, "serve", "s7"))
        self.assertEqual([m.achieved_at for m in ms], sorted(m.achieved_at for m in ms))

    def test_weekly_streak(self):
        self.assertIn("streak_3", keys(compute_milestones([mk(0), mk(7), mk(14)])))
        self.assertNotIn("streak_3", keys(compute_milestones([mk(0), mk(7), mk(28)])))

    def test_shot_total(self):
        self.assertIn("shots_500", keys(compute_milestones([mk(d * 2, n_fh=100) for d in range(5)])))

    def test_session_shots_pb(self):
        ks = keys(compute_milestones([mk(0, n_fh=20), mk(1, n_fh=30)]))
        self.assertIn("pb_shots@s1", ks)

    def test_topspin_pb_needs_20_forehands(self):
        ks = keys(compute_milestones([mk(0, top=0.3), mk(1, n_fh=10, top=0.9), mk(2, top=0.6)]))
        self.assertNotIn("pb_topspin@s1", ks)
        self.assertIn("pb_topspin@s2", ks)

    def test_out_of_order_import_keeps_old_import_ids(self):
        db = Store(":memory:")
        for s in (mk(7, 120), mk(14, 130)):
            db.upsert_session(s)
        i1 = db.begin_import()
        db.sync_milestones(compute_milestones(db.sessions()), i1)
        db.upsert_session(mk(0, 90))  # an older session arrives later
        i2 = db.begin_import()
        added = db.sync_milestones(compute_milestones(db.sessions()), i2)
        ids = {m["key"]: m["import_id"] for m in db.milestones()}
        self.assertEqual(ids["pb_serve@s14"], i1)
        self.assertNotIn("first_session", keys(added))

    def test_resync_adds_nothing(self):
        db = Store(":memory:")
        db.upsert_session(mk(0))
        ms = compute_milestones(db.sessions())
        db.sync_milestones(ms, db.begin_import())
        self.assertEqual(db.sync_milestones(ms, db.begin_import()), [])


if __name__ == "__main__":
    unittest.main()
