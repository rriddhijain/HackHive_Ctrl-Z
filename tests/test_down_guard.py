"""person_down second look (events.down_guard, D87 proposed), alert-first: the alert fires at once as before; a re-look
re-labels it (fighting), retracts it (confident normal, E-9) or confirms it. A re-look that never runs changes nothing.
Unchanged behaviour when the detector vouches for the scene or the guard is off."""
import tempfile
import unittest
from pathlib import Path

from app import events as ev_mod
from app.db import DB
from app.events import EventManager
from app.vlm import CATS

BLIND = {"detector_blind": True, "pair_contact": False, "triggers": set(), "max_persons": 1}
CLEAR = {"detector_blind": False, "pair_contact": False, "triggers": {"person_down"}, "max_persons": 1}
CONTACT = {"detector_blind": False, "pair_contact": True, "triggers": set(), "max_persons": 2}       # overlap only
FIGHT = {"detector_blind": False, "pair_contact": True, "triggers": {"fighting"}, "max_persons": 2}


def C(**kw):
    c = dict.fromkeys(CATS, 0.0); c.update(kw); c["normal"] = max(0.0, 1 - sum(kw.values())); return c


class DownGuard(unittest.TestCase):
    def setUp(self):
        self.g = dict(ev_mod.E["down_guard"])
        ev_mod.E["down_guard"] = {"enabled": True, "blind_frac": 0.5, "verify_s": 10.0}
        self.sent = []
        self.full = []
        self.em = EventManager(DB(Path(tempfile.mkdtemp()) / "t.db"),
                               emit=lambda k, d: (self.sent.append((k, d["category"])), self.full.append((k, dict(d)))))

    def tearDown(self):
        ev_mod.E["down_guard"] = self.g

    def down(self, evidence=BLIND, cam="cam1"):
        # A baseline call (no gate) twice 0.9 person_down -> the window rule opens it.
        self.em.decide(cam, C(person_down=0.9), None, set(), 100, 99, 100.5, evidence=evidence)
        op, _ = self.em.decide(cam, C(person_down=0.9), None, set(), 103, 102, 103.5, evidence=evidence)
        return op

    def status(self, eid):
        return self.em.db.rows("SELECT status, dismiss_reason FROM events WHERE id=?", (eid,))[0]

    def row(self, eid):
        return self.em.db.rows("SELECT * FROM events WHERE id=?", (eid,))[0]

    def log(self):
        return [x[1] for x in self.em.held_log]

    def test_alert_fires_at_once_and_asks_for_relook(self):
        op = self.down()
        self.assertEqual([e["category"] for e in op], ["person_down"])        # no added latency
        self.assertEqual(op[0]["opened_by"], "unverified:detector_blind")
        self.assertIn(("alert", "person_down"), self.sent)
        h = self.em.take_new_hold("cam1")
        self.assertEqual(h["why"], "detector_blind")
        self.assertIsNone(self.em.take_new_hold("cam1"), "one re-look per unverified event")

    def test_relook_fighting_relabels(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)
        self.assertEqual([e["category"] for e in op], ["fighting"])
        self.assertEqual(op[0]["opened_by"], "relook")
        self.assertEqual(op[0]["time_to_alert_ms"], 3000)    # from the original trigger (102 -> 105)
        self.assertTrue(self.em.is_open("cam1", "fighting"))
        self.assertFalse(self.em.is_open("cam1", "person_down"))
        self.assertEqual(self.status(pd["id"]), {"status": "dismissed", "dismiss_reason": "relook"})
        self.assertIn(("event_close", "person_down"), self.sent)

    def test_relook_weak_fighting_still_relabels(self):
        self.down(); self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(fighting=0.5, person_down=0.3), None, set(), 104, 104, 105, relook=True)
        self.assertEqual([e["category"] for e in op], ["fighting"])

    def test_relook_agrees_confirms(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(person_down=0.75), None, set(), 104, 104, 105, relook=True)
        self.assertEqual(op, [])
        self.assertTrue(self.em.is_open("cam1", "person_down"))
        self.assertEqual(pd["opened_by"], "verified")
        self.assertEqual(self.status(pd["id"])["status"], "open")

    def test_relook_confident_normal_retracts(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        self.em.decide("cam1", C(), None, set(), 104, 104, 105, relook=True)
        self.assertFalse(self.em.is_open("cam1", "person_down"))
        self.assertEqual(self.status(pd["id"]), {"status": "dismissed", "dismiss_reason": "relook"})

    def test_relook_unsure_keeps_alert(self):
        self.down(); self.em.take_new_hold("cam1")
        self.em.decide("cam1", C(suspicious_activity=0.35), None, set(), 104, 104, 105, relook=True)
        self.assertTrue(self.em.is_open("cam1", "person_down"))

    def test_no_relook_alert_stands(self):
        self.down(); self.em.take_new_hold("cam1")
        self.em.tick(now=200)                                   # verification expires
        self.assertTrue(self.em.is_open("cam1", "person_down") or self.status(1)["status"] == "closed")
        self.assertNotIn("dismissed", [self.status(1)["status"]])
        self.assertIn("verify_expired", [x[1] for x in self.em.held_log])

    def test_interaction_also_verifies(self):
        op = self.down(FIGHT)
        self.assertEqual(op[0]["opened_by"], "unverified:interaction")
        self.assertEqual(self.em.take_new_hold("cam1")["why"], "interaction")

    def test_box_overlap_alone_does_not_verify(self):
        op = self.down(CONTACT)
        self.assertEqual([e["category"] for e in op], ["person_down"])
        self.assertIsNone(op[0]["opened_by"])
        self.assertIsNone(self.em.take_new_hold("cam1"))

    def test_clear_fall_unchanged(self):
        op, _ = self.em.decide("cam1", C(person_down=0.9), None, {"person_down"}, 100, 99, 100.5, evidence=CLEAR)
        self.assertEqual([e["category"] for e in op], ["person_down"])
        self.assertIsNone(self.em.take_new_hold("cam1"))

    def test_never_fighting_without_a_vote(self):
        self.down(); self.em.take_new_hold("cam1")
        self.em.tick(now=200)
        self.assertFalse(self.em.is_open("cam1", "fighting"))

    def test_disabled_is_old_behaviour(self):
        ev_mod.E["down_guard"] = {"enabled": False}
        op = self.down()
        self.assertEqual([e["category"] for e in op], ["person_down"])
        self.assertIsNone(self.em.take_new_hold("cam1"))

    def test_normal_never_verified(self):
        for t in range(5):
            self.em.decide("cam1", C(), None, set(), 100 + t, 100 + t, evidence=BLIND)
        self.assertIsNone(self.em.take_new_hold("cam1"))

    # --- transparent reclassification: the first alert is never delayed, rewritten or deleted ---

    def test_initial_alert_is_immediate_and_stored(self):
        pd = self.down()[0]
        self.assertEqual(self.sent[0], ("alert", "person_down"))              # the very first thing emitted
        r = self.row(pd["id"])
        self.assertEqual((r["category"], r["status"], r["related_event_id"]), ("person_down", "open", None))
        self.assertEqual(r["time_to_alert_ms"], 1500)                         # 102 -> 103.5: no wait for the re-look

    def test_reclassification_keeps_both_rows_linked(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        fi = self.em.decide("cam1", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)[0][0]
        a, b = self.row(pd["id"]), self.row(fi["id"])
        self.assertEqual(a["category"], "person_down", "the original label is kept, not overwritten")
        self.assertEqual((a["status"], a["dismiss_reason"], a["related_event_id"]), ("dismissed", "relook", fi["id"]))
        self.assertEqual((b["category"], b["status"], b["related_event_id"]), ("fighting", "open", pd["id"]))
        self.assertEqual(self.em.db.rows("SELECT COUNT(*) n FROM events")[0]["n"], 2)
        kinds = [(k, d["category"], d.get("related_event_id")) for k, d in self.full]
        self.assertIn(("alert", "fighting", pd["id"]), kinds)                 # the dashboard learns the link at once
        self.assertIn(("event_close", "person_down", fi["id"]), kinds)
        self.assertIn(f"reclassified:{pd['id']}->{fi['id']}", self.log())

    def test_reclassification_into_an_open_fighting_event(self):
        self.em.decide("cam1", C(fighting=0.9), None, {"fighting"}, 99, 99, 99.5)
        fi_id = self.em.open[("cam1", "fighting")]["id"]
        pd = self.down(BLIND)[0]; self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)
        self.assertEqual(op, [], "no duplicate fighting event")
        self.assertEqual(self.row(pd["id"])["related_event_id"], fi_id)
        self.assertEqual(self.row(fi_id)["related_event_id"], pd["id"])
        self.assertIn(("event_update", "fighting"), self.sent)

    def test_retraction_is_marked_not_deleted(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        self.em.decide("cam1", C(), None, set(), 104, 104, 105, relook=True)
        r = self.row(pd["id"])
        self.assertEqual((r["category"], r["status"], r["dismiss_reason"], r["related_event_id"]),
                         ("person_down", "dismissed", "relook", None))

    def test_relook_after_event_closed_changes_nothing(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        self.em.close_all()
        n = len(self.sent)
        op, sup = self.em.decide("cam1", C(fighting=0.9), None, set(), 104, 104, 105, relook=True)
        self.assertEqual((op, sup), ([], []))
        self.assertEqual(self.status(pd["id"])["status"], "closed")
        self.assertEqual(len(self.sent), n)
        self.assertFalse(self.em.is_open("cam1", "fighting"))

    def test_relook_after_operator_dismissal_changes_nothing(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        self.em.dismiss(pd["id"], now=104)
        self.em.decide("cam1", C(fighting=0.9), None, set(), 104, 104, 105, relook=True)
        self.assertFalse(self.em.is_open("cam1", "fighting"))
        self.assertIn("relook_after_close", self.log())

    def test_camera_removed_while_pending(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        self.em.tick(now=104, down_since={"cam1": 0})                          # pipeline.remove_camera marks it down
        self.assertEqual(self.status(pd["id"])["status"], "closed")
        self.assertNotIn("cam1", self.em.pending)
        self.assertIn("verify_moot", self.log())
        self.assertEqual(self.em.decide("cam1", C(fighting=0.9), None, set(), 105, 105, 106, relook=True), ([], []))

    def test_stale_relook_without_pending_changes_nothing(self):
        before = len(self.em.win["cam1"])
        self.assertEqual(self.em.decide("cam1", C(fighting=0.9), None, set(), 105, 105, 106, relook=True), ([], []))
        self.assertEqual(len(self.em.win["cam1"]), before, "a stale vote never enters the window")
        self.assertIn("relook_stale", self.log())

    def test_duplicate_relook_judges_once(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        self.em.decide("cam1", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)
        op, _ = self.em.decide("cam1", C(fighting=0.8), None, set(), 104.1, 104.1, 105.1, relook=True)
        self.assertEqual(op, [])
        self.assertEqual(self.em.db.rows("SELECT COUNT(*) n FROM events WHERE category='fighting'")[0]["n"], 1)

    def test_repeated_frames_do_not_reopen_or_requeue(self):
        self.down(); self.em.take_new_hold("cam1")
        for k in range(5):                                                       # the same frozen frame, re-observed
            op, _ = self.em.decide("cam1", C(person_down=0.9), None, set(), 103, 102, 103.5 + k, evidence=BLIND)
            self.assertEqual(op, [])
        self.assertIsNone(self.em.take_new_hold("cam1"))
        self.assertEqual(self.em.db.rows("SELECT COUNT(*) n FROM events")[0]["n"], 1)

    def test_cameras_verified_independently(self):
        a = self.down(cam="cam1")[0]; b = self.down(cam="cam2")[0]
        self.assertEqual({self.em.take_new_hold("cam1")["eid"], self.em.take_new_hold("cam2")["eid"]}, {a["id"], b["id"]})
        fi = self.em.decide("cam2", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)[0][0]
        self.assertEqual(fi["camera_id"], "cam2")
        self.assertTrue(self.em.is_open("cam1", "person_down"))
        self.assertEqual(self.status(a["id"])["status"], "open")
        self.assertEqual(self.status(b["id"])["status"], "dismissed")
        self.em.decide("cam1", C(person_down=0.8), None, set(), 104, 104, 105, relook=True)
        self.assertEqual(a["opened_by"], "verified")

    def test_no_new_unverified_person_down_while_its_fight_is_open(self):
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        fi = self.em.decide("cam1", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)[0][0]
        for t in range(3):                                  # the model keeps reading the blind scene as person_down
            op, _ = self.em.decide("cam1", C(person_down=0.9), None, set(), 106 + t, 106 + t, 106.5 + t, evidence=BLIND)
            self.assertEqual(op, [])
        self.assertEqual(self.row(fi["id"])["related_event_id"], pd["id"], "the link still points at the original")
        self.assertIn(f"covered_by:{fi['id']}", self.log())
        op, _ = self.em.decide("cam1", C(person_down=0.9), None, {"person_down"}, 110, 110, 110.5, evidence=CLEAR)
        self.assertEqual([e["category"] for e in op], ["person_down"], "a fall the detector vouches for still alerts")

    def test_relook_fighting_respects_operator_hold(self):
        self.em.decide("cam1", C(fighting=0.9), None, {"fighting"}, 99, 99, 99.5)
        self.em.dismiss(self.em.open[("cam1", "fighting")]["id"], now=99.6)    # operator: that fight was a false alarm
        pd = self.down()[0]; self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)
        self.assertEqual(op, [])
        self.assertEqual(self.status(pd["id"])["status"], "open")
        self.assertNotEqual(pd["opened_by"], "verified")

    def test_old_db_gains_the_link_column(self):
        import sqlite3
        p = Path(tempfile.mkdtemp()) / "old.db"
        from app.db import SCHEMA
        old = SCHEMA.replace(", related_event_id INTEGER", "")                 # the schema as main ships it
        self.assertNotEqual(old, SCHEMA)
        con = sqlite3.connect(p)
        con.executescript(old)
        con.execute("INSERT INTO events (camera_id, category, start_ts, status) VALUES ('cam1', 'fighting', 1, 'closed')")
        con.commit(); con.close()
        db = DB(p)
        self.assertIn("related_event_id", {r[1] for r in db.con.execute("PRAGMA table_info(events)")})
        self.assertEqual(db.rows("SELECT category, related_event_id FROM events"), [{"category": "fighting", "related_event_id": None}])


if __name__ == "__main__":
    unittest.main()
