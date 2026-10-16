"""Seeded history for the demo chat (P4, E-19): past events on 4 cameras over the last 24 h, all marked seeded=1.

  uv run python -m scripts.seed_history            insert (times relative to now; replaces earlier seeded rows)
  uv run python -m scripts.seed_history --remove   delete every seeded row

Seeded cameras use readable ids (lobby, parking_lot, ...) so they never collide with live ids (cam1, cam2, ...).
Rows are in time order, so in an empty DB the ids are 1..23 in order, then #24 (dismissed). bench/chat_questions.csv
relies on that.
"""
import sys

from app.vlm import severity

# (minutes before now, camera, category, subtype, peak confidence, duration s, summary). now = 06:00 IST in the runner.
EVENTS = [
    (1430, "loading_dock", "suspicious_activity", "loitering", .72, 300, "A man in a grey hoodie lingers by the loading bay shutter for several minutes."),
    (1315, "lobby", "tailgating", None, .88, 6, "A second person in a blue jacket follows a staff member through the turnstile on one card swipe."),
    (1220, "parking_lot", "property_damage", "vandalism", .81, 40, "A person kicks the side mirror off a parked white car."),
    (1120, "lobby", "crowd_incident", "gathering", .77, 420, "A large group gathers at the reception desk and blocks the entrance."),
    (1015, "server_room", "suspicious_activity", "trespass", .90, 60, "Someone without a badge enters the server room behind a technician."),
    (930, "loading_dock", "property_damage", "falling_object", .86, 15, "A stacked crate falls off a forklift pallet onto the floor."),
    (795, "parking_lot", "fighting", None, .93, 90, "Two men push and punch each other between parked cars."),
    (710, "lobby", "person_down", None, .89, 120, "An elderly woman slips near the entrance and stays on the floor."),
    (630, "loading_dock", "fire_smoke", "smoke", .84, 180, "Grey smoke rises from a bin next to the loading bay door."),
    (525, "parking_lot", "suspicious_activity", "theft", .79, 150, "A person tries car door handles along the row and opens one."),
    (440, "lobby", "suspicious_activity", "abandoned_object", .75, 660, "A black backpack is left under the lobby bench for over ten minutes."),
    (365, "server_room", "tailgating", None, .83, 5, "A visitor follows an engineer through the server room door without swiping."),
    (310, "parking_lot", "suspicious_activity", "loitering", .70, 360, "Two people loiter near the exit barrier for several minutes."),
    (265, "loading_dock", "fighting", None, .91, 45, "Two workers shove each other near the forklift and one throws a punch."),
    (230, "lobby", "suspicious_activity", "weapon", .87, 30, "A man in a blue jacket shows a knife at the reception desk."),
    (200, "lobby", "fighting", None, .92, 70, "The man in the blue jacket wrestles with a security guard by the turnstile."),
    (185, "parking_lot", "crowd_incident", "running", .78, 25, "A group suddenly runs out of the car park toward the street."),
    (150, "server_room", "fire_smoke", "smoke", .85, 240, "Smoke comes from a cable tray above rack 4."),
    (100, "loading_dock", "person_down", None, .90, 200, "A worker falls from the loading ramp and lies still on the ground."),
    (55, "lobby", "tailgating", None, .86, 6, "A courier follows a staff member through the main door on one swipe."),
    (25, "parking_lot", "property_damage", "breakage", .82, 20, "A car window is smashed and glass lies beside the barrier."),
    (8, "loading_dock", "suspicious_activity", "abandoned_object", .74, 240, "An unattended suitcase sits beside the loading bay door."),
    (4, "lobby", "person_down", None, .88, 120, "A man collapses near the lift and does not get up."),
    (70, "server_room", "fighting", None, .71, 20, "Two technicians play-fight by the racks."),   # #24, dismissed by an operator
]
NORMAL = [  # observations with no event (keyword search falls back to these when no event matches)
    (180, "parking_lot", "A delivery van parks near the exit barrier."),
    (20, "lobby", "A cleaner mops the lobby floor near the lift."),
]


def remove(db):
    with db.lock:
        n = db.con.execute("DELETE FROM events WHERE seeded=1").rowcount
        db.con.execute("DELETE FROM observations WHERE seeded=1")
    return n


def seed(db, now):
    remove(db)
    for i, (ago, cam, cat, sub, conf, dur, summ) in enumerate(EVENTS):
        t = now - ago * 60
        dismissed = i == 23
        eid = db.insert("events", {"camera_id": cam, "category": cat, "subtype": sub, "severity": severity(cat, sub),
                                   "start_ts": t, "end_ts": t + dur, "peak_confidence": conf, "summary": summ,
                                   # an earlier shift's alerts were acknowledged; the last hour's are not yet (FR-17 follow-up)
                                   "status": "dismissed" if dismissed else "acknowledged" if ago > 60 else "closed",
                                   "dismiss_reason": "operator" if dismissed else None, "n_obs": 1, "seeded": 1})
        db.insert("observations", {"camera_id": cam, "ts": t, "category": cat, "subtype": sub, "confidence": conf,
                                   "summary": summ, "event_id": eid, "seeded": 1})
    for ago, cam, summ in NORMAL:
        db.insert("observations", {"camera_id": cam, "ts": now - ago * 60, "category": "normal", "confidence": .9,
                                   "summary": summ, "seeded": 1})
    return len(EVENTS)


if __name__ == "__main__":
    import time

    from app.db import DB
    db = DB()
    if "--remove" in sys.argv:
        print(f"removed {remove(db)} seeded events")
    else:
        print(f"seeded {seed(db, time.time())} events on 4 cameras (remove: uv run python -m scripts.seed_history --remove)")
