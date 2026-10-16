"""SQLite (WAL) store for observations and events (SPEC §8, §5a step 9). JSON-valued columns are stored as JSON text.
The FTS5 tables (§8) are external-content tables: triggers keep them in sync, and every open rebuilds them once (rows
written before the triggers existed). Chat searches them (P4, D53)."""
import json
import sqlite3
import threading

from app.config import ROOT

PATH = ROOT / "data" / "hackhive.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY, camera_id TEXT NOT NULL, ts REAL NOT NULL,
  category TEXT NOT NULL, subtype TEXT, confidence REAL, probs TEXT, summary TEXT, people_count INTEGER,
  trigger TEXT, track_ids TEXT, thumb_path TEXT, event_id INTEGER, model TEXT, timing TEXT, seeded INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_obs_cam_ts ON observations(camera_id, ts);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, camera_id TEXT NOT NULL, category TEXT NOT NULL, subtype TEXT, severity TEXT,
  start_ts REAL NOT NULL, end_ts REAL, peak_confidence REAL, summary TEXT, keyframe_paths TEXT,
  track_ids TEXT, status TEXT DEFAULT 'open', dismiss_reason TEXT, n_obs INTEGER DEFAULT 1,
  time_to_alert_ms INTEGER, latency_ms INTEGER, seeded INTEGER DEFAULT 0, related_event_id INTEGER);
CREATE INDEX IF NOT EXISTS idx_evt_cam_ts ON events(camera_id, start_ts);
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(summary, category, content='events', content_rowid='id', tokenize='porter unicode61');   -- D74: push = pushed = pushing
CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(summary, content='observations', content_rowid='id', tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
  INSERT INTO events_fts(rowid, summary, category) VALUES (new.id, new.summary, new.category); END;
CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
  INSERT INTO events_fts(events_fts, rowid, summary, category) VALUES ('delete', old.id, old.summary, old.category); END;
CREATE TRIGGER IF NOT EXISTS events_au AFTER UPDATE OF summary, category ON events BEGIN
  INSERT INTO events_fts(events_fts, rowid, summary, category) VALUES ('delete', old.id, old.summary, old.category);
  INSERT INTO events_fts(rowid, summary, category) VALUES (new.id, new.summary, new.category); END;
CREATE TRIGGER IF NOT EXISTS obs_ai AFTER INSERT ON observations BEGIN
  INSERT INTO observations_fts(rowid, summary) VALUES (new.id, new.summary); END;
CREATE TRIGGER IF NOT EXISTS obs_ad AFTER DELETE ON observations BEGIN
  INSERT INTO observations_fts(observations_fts, rowid, summary) VALUES ('delete', old.id, old.summary); END;
CREATE TRIGGER IF NOT EXISTS obs_au AFTER UPDATE OF summary ON observations BEGIN
  INSERT INTO observations_fts(observations_fts, rowid, summary) VALUES ('delete', old.id, old.summary);
  INSERT INTO observations_fts(rowid, summary) VALUES (new.id, new.summary); END;
INSERT INTO events_fts(events_fts) VALUES ('rebuild');
INSERT INTO observations_fts(observations_fts) VALUES ('rebuild');
"""
JSON_COLS = {"probs", "track_ids", "timing", "keyframe_paths"}
OBS_COLS = ["camera_id", "ts", "category", "subtype", "confidence", "probs", "summary", "people_count", "trigger",
            "track_ids", "thumb_path", "event_id", "model", "timing", "seeded"]
EVT_COLS = ["camera_id", "category", "subtype", "severity", "start_ts", "end_ts", "peak_confidence", "summary",
            "keyframe_paths", "track_ids", "status", "dismiss_reason", "n_obs", "time_to_alert_ms", "latency_ms", "seeded",
            "related_event_id"]   # D87: a re-look re-label links the original alert and its replacement both ways


class DB:
    def __init__(self, path=PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False, isolation_level=None)  # autocommit
        self.con.execute("PRAGMA journal_mode=WAL")
        old = self.con.execute("SELECT sql FROM sqlite_master WHERE name='events_fts'").fetchone()
        if old and "porter" not in old[0]:          # a pre-D74 DB: recreate the FTS tables with the stemmer (rebuilt below)
            self.con.executescript("DROP TABLE events_fts; DROP TABLE observations_fts;")
        if self.con.execute("SELECT name FROM sqlite_master WHERE name='events'").fetchone():
            cols = {r[1] for r in self.con.execute("PRAGMA table_info(events)")}
            if "related_event_id" not in cols:      # a pre-D87 DB file: add the column, keep every row
                self.con.execute("ALTER TABLE events ADD COLUMN related_event_id INTEGER")
        self.con.executescript(SCHEMA)
        self.lock = threading.Lock()

    def _vals(self, cols, row):
        return [json.dumps(row.get(c)) if c in JSON_COLS and row.get(c) is not None else row.get(c, 0 if c == "seeded" else None)
                for c in cols]

    def insert(self, table, row):
        cols = OBS_COLS if table == "observations" else EVT_COLS
        with self.lock:
            cur = self.con.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                                   self._vals(cols, row))
        return cur.lastrowid

    def update(self, table, id_, row):
        cols = [c for c in row if c in (OBS_COLS if table == "observations" else EVT_COLS)]
        with self.lock:
            self.con.execute(f"UPDATE {table} SET {','.join(c + '=?' for c in cols)} WHERE id=?", self._vals(cols, row) + [id_])

    def rows(self, sql, args=()):
        with self.lock:
            cur = self.con.execute(sql, args)
            names = [d[0] for d in cur.description]
            return [{n: json.loads(v) if n in JSON_COLS and v else v for n, v in zip(names, r)} for r in cur.fetchall()]

    def reset_live(self):
        """replay.reset_live_tables_on_start: drop live rows, keep seeded history (E-14)."""
        with self.lock:
            self.con.execute("DELETE FROM observations WHERE seeded=0")
            self.con.execute("DELETE FROM events WHERE seeded=0")


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    db = DB(tmp)
    assert db.con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    eid = db.insert("events", {"camera_id": "cam1", "category": "fighting", "severity": "critical", "start_ts": 1.0,
                               "peak_confidence": 0.9, "track_ids": [3, 5], "status": "open"})
    oid = db.insert("observations", {"camera_id": "cam1", "ts": 1.0, "category": "fighting", "confidence": 0.9,
                                     "probs": {"fighting": 0.9, "normal": 0.1}, "event_id": eid, "timing": {"t_capture": 1.0}})
    db.update("events", eid, {"summary": "Two people shoving.", "n_obs": 2, "status": "closed"})
    e = db.rows("SELECT * FROM events")[0]; o = db.rows("SELECT * FROM observations")[0]
    assert e["track_ids"] == [3, 5] and e["n_obs"] == 2 and e["status"] == "closed" and e["seeded"] == 0, e
    assert o["probs"]["fighting"] == 0.9 and o["event_id"] == eid and o["timing"]["t_capture"] == 1.0, o
    db.insert("events", {"camera_id": "cam9", "category": "normal", "start_ts": 0.0, "seeded": 1})
    fts = lambda q: [r["rowid"] for r in db.rows("SELECT rowid FROM events_fts WHERE events_fts MATCH ?", (q,))]
    assert fts("shoving") == [eid] and fts("fighting") == [eid], fts("shoving")   # insert + update kept in sync
    assert fts("shoved") == [eid] and fts("shove") == [eid], fts("shoved")          # D74: Porter stemming
    db.reset_live()
    assert [r["camera_id"] for r in db.rows("SELECT camera_id FROM events")] == ["cam9"]
    assert fts("shoving") == [] and DB(tmp).rows("SELECT count(*) n FROM events_fts")[0]["n"] == 1   # delete + reopen
    old = Path(tempfile.mkdtemp()) / "old.db"       # D74 migration: a DB made before stemming is upgraded on open
    con = sqlite3.connect(old)
    con.executescript(SCHEMA.replace(", tokenize='porter unicode61'", "").split("INSERT INTO events_fts(events_fts)")[0])
    con.execute("INSERT INTO events (camera_id, category, start_ts, summary) VALUES ('cam1', 'fighting', 1.0, 'One is pushed back.')")
    con.commit(); con.close()
    assert [r["rowid"] for r in DB(old).rows("SELECT rowid FROM events_fts WHERE events_fts MATCH 'pushing'")] == [1]
    print("db self-check ok")
