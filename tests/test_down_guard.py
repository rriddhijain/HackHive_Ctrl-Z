"""person_down second look (events.down_guard, D83 proposed): held, resolved by a re-look, fail-safe timeout,
and unchanged behaviour when the detector vouches for the scene or the guard is off."""
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
        ev_mod.E["down_guard"] = {"enabled": True, "blind_frac": 0.5, "hold_s": 4.0}
        self.em = EventManager(DB(Path(tempfile.mkdtemp()) / "t.db"))

    def tearDown(self):
        ev_mod.E["down_guard"] = self.g

    def hold(self, evidence=BLIND, cam="cam1"):
        # A baseline call (no gate) twice 0.9 person_down -> the window rule would open it; the guard holds it instead.
        self.em.decide(cam, C(person_down=0.9), None, set(), 100, 99, 100.5, evidence=evidence)
        op, _ = self.em.decide(cam, C(person_down=0.9), None, set(), 103, 102, 103.5, evidence=evidence)
        return op

    def test_blind_detector_holds_and_asks_for_relook(self):
        self.assertEqual(self.hold(), [])
        self.assertFalse(self.em.is_open("cam1", "person_down"))
        h = self.em.take_new_hold("cam1")
        self.assertEqual(h["why"], "detector_blind")
        self.assertIsNone(self.em.take_new_hold("cam1"), "one re-look request per hold")

    def test_relook_fighting_opens_fighting(self):
        self.hold(); self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(fighting=0.8), None, set(), 104, 104, 105, relook=True)
        self.assertEqual([e["category"] for e in op], ["fighting"])
        self.assertEqual(op[0]["opened_by"], "relook")
        self.assertEqual(op[0]["time_to_alert_ms"], 3000)   # timed from the held observation's trigger (102 -> 105)
        self.assertFalse(self.em.is_open("cam1", "person_down"))

    def test_relook_agrees_opens_person_down(self):
        self.hold(); self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(person_down=0.75), None, set(), 104, 104, 105, relook=True)
        self.assertEqual([e["category"] for e in op], ["person_down"])

    def test_relook_confident_normal_drops_hold(self):
        self.hold(); self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(), None, set(), 104, 104, 105, relook=True)
        self.assertEqual(op, [])
        self.assertEqual(self.em.tick(now=200), [])
        self.assertFalse(self.em.is_open("cam1", "person_down"))
        self.assertEqual(list(self.em.late_opened), [])
        self.assertIn("hold_dropped", [x[1] for x in self.em.held_log])

    def test_relook_unsure_keeps_first_vote(self):
        self.hold(); self.em.take_new_hold("cam1")
        op, _ = self.em.decide("cam1", C(suspicious_activity=0.35), None, set(), 104, 104, 105, relook=True)
        self.assertEqual([e["category"] for e in op], ["person_down"])

    def test_timeout_opens_person_down(self):
        self.hold(); self.em.take_new_hold("cam1")
        self.em.tick(now=106)                               # deadline 103.5 + 4 = 107.5: not yet
        self.assertFalse(self.em.is_open("cam1", "person_down"))
        self.em.tick(now=108)
        self.assertTrue(self.em.is_open("cam1", "person_down"))
        late = list(self.em.late_opened)
        self.assertEqual([(e["category"], e["opened_by"]) for e in late], [("person_down", "hold_timeout")])

    def test_interaction_also_holds(self):
        self.assertEqual(self.hold(FIGHT), [])
        self.assertEqual(self.em.take_new_hold("cam1")["why"], "interaction")

    def test_box_overlap_alone_does_not_hold(self):
        # People at different depths overlap on screen all the time: that alone must not delay a fall.
        self.assertEqual([e["category"] for e in self.hold(CONTACT)], ["person_down"])

    def test_clear_fall_unchanged(self):
        # Detector sees the person, no contact, person_down gate fired: opens on the first observation, as before.
        op, _ = self.em.decide("cam1", C(person_down=0.9), None, {"person_down"}, 100, 99, 100.5, evidence=CLEAR)
        self.assertEqual([e["category"] for e in op], ["person_down"])
        self.assertIsNone(self.em.take_new_hold("cam1"))

    def test_guard_never_turns_down_into_fighting_by_itself(self):
        self.hold()
        self.em.tick(now=108)
        self.assertFalse(self.em.is_open("cam1", "fighting"))

    def test_disabled_is_old_behaviour(self):
        ev_mod.E["down_guard"] = {"enabled": False}
        self.assertEqual([e["category"] for e in self.hold()], ["person_down"])

    def test_normal_never_held(self):
        for t in range(5):
            self.em.decide("cam1", C(), None, set(), 100 + t, 100 + t, evidence=BLIND)
        self.assertIsNone(self.em.take_new_hold("cam1"))


if __name__ == "__main__":
    unittest.main()
