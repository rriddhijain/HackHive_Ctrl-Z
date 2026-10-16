"""Chat v1 (SPEC §5a.2, §7.5, FR-8b, FR-18, D53, D57): rules -> SQL / FTS5 -> answer.

list / count / latest / detail are templates (no model call); every event in the answer is cited as [#id].
summary: the model at arbiter priority P2 (below gate-triggered calls, which preempt it) with <= 30 rows, then a
sentence-by-sentence check: unknown [#id]s are removed, sentences left without a valid [#id] are dropped; nothing left
-> the template list. No rows -> "No matching events" + the filters. Facts only ever come from stored rows.
Not built (v1): model extraction when the rules can't parse (§5a.2 step 3); unknown intent is `list`, leftover words
are keywords.
"""
import datetime as dt
import json
import re
import threading
import time
from zoneinfo import ZoneInfo

import httpx

from app.vlm import CATS, V

IST = ZoneInfo("Asia/Kolkata")
LIMIT = {"list": 20, "count": 200, "latest": 1, "detail": 1, "summary": 30}
MODEL_WAIT_S = 10            # chat waits at most this for the model (queue behind P1s + call), then answers by template
SYN = {  # question word(s) -> (category, subtype or None); two-word phrases are matched first
    "person down": ("person_down", None), "man down": ("person_down", None), "fall": ("person_down", None),
    "falls": ("person_down", None), "fell": ("person_down", None), "fallen": ("person_down", None),
    "collapse": ("person_down", None), "collapsed": ("person_down", None), "collapses": ("person_down", None),
    "fainted": ("person_down", None), "unconscious": ("person_down", None),
    "fire": ("fire_smoke", None), "fires": ("fire_smoke", None), "smoke": ("fire_smoke", "smoke"),
    "flames": ("fire_smoke", "fire"), "burning": ("fire_smoke", None),
    "fight": ("fighting", None), "fights": ("fighting", None), "fighting": ("fighting", None), "brawl": ("fighting", None),
    "assault": ("fighting", None), "punch": ("fighting", None), "punching": ("fighting", None), "violence": ("fighting", None),
    "crowd": ("crowd_incident", None), "crowds": ("crowd_incident", None), "crowding": ("crowd_incident", None),
    "gathering": ("crowd_incident", "gathering"), "stampede": ("crowd_incident", "running"),
    "property damage": ("property_damage", None), "damage": ("property_damage", None), "vandalism": ("property_damage", "vandalism"),
    "broken": ("property_damage", "breakage"), "breakage": ("property_damage", "breakage"),
    "falling object": ("property_damage", "falling_object"),
    "suspicious": ("suspicious_activity", None), "loitering": ("suspicious_activity", "loitering"),
    "theft": ("suspicious_activity", "theft"), "thefts": ("suspicious_activity", "theft"), "stealing": ("suspicious_activity", "theft"),
    "shoplifting": ("suspicious_activity", "theft"), "trespass": ("suspicious_activity", "trespass"),
    "trespassing": ("suspicious_activity", "trespass"), "intruder": ("suspicious_activity", "trespass"),
    "weapon": ("suspicious_activity", "weapon"), "weapons": ("suspicious_activity", "weapon"),
    "knife": ("suspicious_activity", "weapon"), "gun": ("suspicious_activity", "weapon"),
    "abandoned": ("suspicious_activity", "abandoned_object"), "unattended": ("suspicious_activity", "abandoned_object"),
    "tailgating": ("tailgating", None), "tailgate": ("tailgating", None), "piggybacking": ("tailgating", None),
    **{c: (c, None) for c in CATS if c != "normal"}, **{c.replace("_", " "): (c, None) for c in CATS if c != "normal"},
}
STOP = set("""a an the and or of on in at to for from by with without near any anything something some all every each
is are was were be been being has have had do did does doing done there here this that these those it its it's i me my
we us our you your he she they them their what which who whom whose when where why how show list tell give find get see
seen saw spot spotted catch caught display let lets please can could would should will shall may might must about
event events incident incidents alert alerts happen happened happening occur occurred going on camera cameras cam cams
footage recorded record details detail info information involving involve involved regarding related
many much count number often latest last recent most newest summary summarise summarize overview recap brief describe
report time times today yesterday ago since before after between until up out over just also only again more
someone somebody anyone anybody everyone everybody person persons people individual individuals guy guys
one two three four being got""".split())   # D74: filler words are never required keywords
GENERIC = {"camera", "cam", "live", "recorded", "webcam", "video", "room", "area", "view", "the", "avi", "mp4", "mov", "mkv"}
CLK = r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?"


def fmt(ts):
    return dt.datetime.fromtimestamp(ts, IST).strftime("%d %b %H:%M")


def display(cid, names):
    return names.get(cid) or cid.replace("_", " ").title()


def cam_names(db, live=None):
    """id -> display name: every camera with stored events (seeded slugs prettified) + this session's live names."""
    ids = [r["camera_id"] for r in db.rows("SELECT DISTINCT camera_id FROM events")]
    return {i: display(i, {}) for i in ids} | (live or {})


def _clock(h, m, ap):
    h, m = int(h), int(m or 0)
    if ap:
        h = h % 12 + (12 if ap[0] == "p" else 0)
    return h, m


def parse(question, names, now):
    """Rules only (§5a.2 steps 2 + 4). Returns the §7.5 filters (+ subtypes, unknown_cameras)."""
    q = " " + re.sub(r"\bnoon\b", "12 pm", re.sub(r"\bmidnight\b", "12 am", question.lower().replace("?", " "))) + " "
    f = {"intent": None, "cameras": [], "categories": [], "subtypes": [], "t_from": None, "t_to": None,
         "keywords": None, "event_id": None, "limit": None, "unknown_cameras": []}

    def cut(m):                                 # matched spans never become keywords
        nonlocal q
        q = q[:m.start()] + " " + q[m.end():]

    if m := re.search(r"(?:#|\b(?:event|incident|alert|id)\s+#?)(\d+)\b", q):
        f["event_id"] = int(m[1]); cut(m)
    # time (IST)
    nowd = dt.datetime.fromtimestamp(now, IST)
    day = nowd.replace(hour=0, minute=0, second=0, microsecond=0)
    explicit_day = False
    if m := re.search(r"\byesterday\b", q):
        day -= dt.timedelta(days=1); explicit_day = True; cut(m)
        f["t_from"], f["t_to"] = day.timestamp(), (day + dt.timedelta(days=1)).timestamp()
    elif m := re.search(r"\btoday\b", q):
        explicit_day = True; cut(m)
        f["t_from"], f["t_to"] = day.timestamp(), now
    at = lambda hm: day + dt.timedelta(hours=hm[0], minutes=hm[1])
    rng = None
    if m := re.search(r"\b(?:last|past)\s+(\d+|an?|one)?\s*(minutes?|mins?|hours?|hrs?|days?)\b", q):
        n = int(m[1]) if m[1] and m[1].isdigit() else 1
        f["t_from"], f["t_to"] = now - n * {"m": 60, "h": 3600, "d": 86400}[m[2][0]], now; cut(m)
    elif m := re.search(r"\blast night\b|\bovernight\b", q):
        f["t_from"], f["t_to"] = (day - dt.timedelta(hours=2)).timestamp(), (day + dt.timedelta(hours=6)).timestamp(); cut(m)
    elif m := re.search(rf"\b(?:between|from)\s+{CLK}\s+(?:and|to|-)\s+{CLK}", q):
        ap = m[3] or m[6]
        rng = at(_clock(m[1], m[2], ap)), at(_clock(m[4], m[5], m[6] or ap)); cut(m)
    elif m := re.search(rf"\b(?:since|after)\s+{CLK}", q):
        rng = at(_clock(*m.groups())), None; cut(m)
    elif m := re.search(rf"\bbefore\s+{CLK}", q):
        rng = day, at(_clock(*m.groups())); cut(m)
    elif m := re.search(rf"\b(?:at|around)\s+{CLK}", q):
        a = at(_clock(*m.groups())); rng = a - dt.timedelta(minutes=15), a + dt.timedelta(minutes=15); cut(m)
    elif m := re.search(r"\b(?:this\s+)?(morning|afternoon|evening|tonight)\b", q):
        h = {"morning": (6, 12), "afternoon": (12, 17), "evening": (17, 22), "tonight": (17, 24)}[m[1]]
        rng = day + dt.timedelta(hours=h[0]), day + dt.timedelta(hours=h[1]); cut(m)
    if rng:
        a, b = rng
        if b is not None and b <= a:
            b += dt.timedelta(days=1)           # "between 10 pm and 2 am"
        if not explicit_day and a.timestamp() > now:
            a -= dt.timedelta(days=1); b = b and b - dt.timedelta(days=1)   # a clock time still to come = yesterday's
        f["t_from"], f["t_to"] = a.timestamp(), min(b.timestamp(), now) if b else now
    # cameras: "camera 2" / "cam2", then known names, then "<word> camera" that names no known camera
    for m in list(re.finditer(r"\bcam(?:era)?\s*#?(\d+)\b", q))[::-1]:
        f["cameras"].append(f"cam{m[1]}"); cut(m)
    for cid, nm in names.items():
        words = [w for w in re.findall(r"[a-z0-9]+", nm.lower()) if w not in GENERIC]
        phrases = {cid.lower(), cid.lower().replace("_", " "), " ".join(words)} | {w for w in words if len(w) >= 4 and not w.isdigit()}
        for p in sorted(filter(None, phrases), key=len, reverse=True):
            if m := re.search(rf"\b{re.escape(p)}\b", q):
                f["cameras"].append(cid); cut(m)
                for m2 in list(re.finditer(rf"\b{re.escape(p)}\b", q))[::-1]:
                    cut(m2)
                break
    for m in list(re.finditer(r"\b([a-z]+)\s+cam(?:era)?s?\b", q))[::-1]:
        if m[1] not in STOP:
            f["unknown_cameras"].append(m[1])
        cut(m)
    # categories (two-word phrases first)
    for p in sorted(SYN, key=lambda k: -len(k)):
        if m := re.search(rf"\b{re.escape(p)}\b", q):
            cat, sub = SYN[p]
            if cat not in f["categories"]:
                f["categories"].append(cat)
            if sub and sub not in f["subtypes"]:
                f["subtypes"].append(sub)
            cut(m)
    if f["subtypes"] and any(not SYN[p][1] for p in SYN if re.search(rf"\b{re.escape(p)}\b", question.lower())):
        f["subtypes"] = []                      # "fire or smoke": a bare category word widens back to the category
    # intent (on the question; time spans are cut first, so "last 10 minutes" is not "latest")
    if f["event_id"] is not None:
        f["intent"] = "detail"
    elif re.search(r"\bhow many\b|\bcount\b|\bnumber of\b|\bhow often\b", q):
        f["intent"] = "count"
    elif re.search(r"\bsummar|\boverview\b|\bwhat happened\b|\bwhat did\b|\bwhat went on\b|\brecap\b|\bbrief\b|\bdescribe\b", q):
        f["intent"] = "summary"
    elif re.search(r"\blatest\b|\bmost recent\b|\bnewest\b|\blast\b", q):
        f["intent"] = "latest"
    else:
        f["intent"] = "list"
    kw = [w for w in re.findall(r"[a-z0-9]+", q) if len(w) >= 3 and w not in STOP]
    f["keywords"] = kw or None
    f["limit"] = LIMIT[f["intent"]]
    return f


def fts_query(words):
    """FTS5 query: every keyword must appear, quoted so user text can't inject syntax. The Porter tokenizer (D74)
    stems both sides, so push / pushed / pushing and jacket / jackets match. No any-word fallback: "red jacket"
    must not return the blue-jacket events (a grounded "no match" beats a near miss)."""
    return " AND ".join(f'"{w}"' for w in words)


def retrieve(db, f):
    if f["event_id"] is not None:
        return db.rows("SELECT * FROM events WHERE id=? AND status!='dismissed'", (f["event_id"],)), []
    cl, args = ["status != 'dismissed'"], []
    for col, vals in (("camera_id", f["cameras"] + f["unknown_cameras"]), ("category", f["categories"]), ("subtype", f["subtypes"])):
        if vals:
            cl.append(f"{col} IN ({','.join('?' * len(vals))})"); args += vals
    if f["t_from"] is not None:
        cl.append("start_ts >= ?"); args.append(f["t_from"])
    if f["t_to"] is not None:
        cl.append("start_ts <= ?"); args.append(f["t_to"])
    obs = []
    if f["keywords"]:
        q = fts_query(f["keywords"])
        cl.append("(id IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?) OR id IN (SELECT event_id FROM observations"
                  " WHERE event_id IS NOT NULL AND id IN (SELECT rowid FROM observations_fts WHERE observations_fts MATCH ?)))")
        args += [q, q]
    rows = db.rows(f"SELECT * FROM events WHERE {' AND '.join(cl)} ORDER BY start_ts DESC LIMIT ?", args + [f["limit"]])
    if not rows and f["keywords"]:              # §5a.2 step 5: nothing matched -> observations that mention it
        ocl, oargs = ["id IN (SELECT rowid FROM observations_fts WHERE observations_fts MATCH ?)"], [fts_query(f["keywords"])]
        if f["cameras"] or f["unknown_cameras"]:
            c = f["cameras"] + f["unknown_cameras"]
            ocl.append(f"camera_id IN ({','.join('?' * len(c))})"); oargs += c
        for op, v in ((">=", f["t_from"]), ("<=", f["t_to"])):
            if v is not None:
                ocl.append(f"ts {op} ?"); oargs.append(v)
        obs = db.rows(f"SELECT * FROM observations WHERE {' AND '.join(ocl)} ORDER BY ts DESC LIMIT 3", oargs)
    return rows, obs


def describe(f, names):
    parts = [display(c, names) for c in f["cameras"]] + [c.replace("_", " ") for c in f["categories"]]
    parts += [s.replace("_", " ") for s in f["subtypes"]]
    if f["keywords"]:
        parts.append("keywords: " + " ".join(f["keywords"]))
    if f["t_from"] is not None:
        parts.append(f"{fmt(f['t_from'])}–{fmt(f['t_to'])} IST")
    else:
        parts.append("all time")
    return " · ".join(parts)


def line(e, names):
    sev = e["severity"] or "–"
    what = e["category"].replace("_", " ") + (f" / {e['subtype'].replace('_', ' ')}" if e.get("subtype") else "")
    return (f"[#{e['id']}] {fmt(e['start_ts'])} · {display(e['camera_id'], names)} · {what} "
            f"({sev}, {round((e['peak_confidence'] or 0) * 100)}%): {e['summary'] or 'no summary'}")


def template(f, rows, names, total=None):
    if f["intent"] == "count":
        by = {}
        for e in rows:
            by[e["category"]] = by.get(e["category"], 0) + 1
        split = ", ".join(f"{n} {c.replace('_', ' ')}" for c, n in sorted(by.items(), key=lambda kv: -kv[1]))
        return f"{len(rows)} events ({describe(f, names)}): {split}. " + " ".join(f"[#{e['id']}]" for e in rows)
    if f["intent"] == "latest":
        return "Latest: " + line(rows[0], names)
    if f["intent"] == "detail":
        e = rows[0]
        end = f"–{fmt(e['end_ts'])[-5:]}" if e.get("end_ts") else ""
        return (line(e, names).replace(fmt(e["start_ts"]), fmt(e["start_ts"]) + end, 1) +
                f" Status {e['status']}, {e['n_obs']} observation{'s' if e['n_obs'] != 1 else ''}"
                f"{', seeded history' if e.get('seeded') else ''}.")
    head = f"{len(rows)} event{'s' if len(rows) != 1 else ''} ({describe(f, names)})"
    if total and total > len(rows):
        head += f", newest {len(rows)} of {total}"
    return head + ":\n" + "\n".join(line(e, names) for e in rows)


def ground(text, ids):
    """D57: keep only cited [#id]s that are in `ids`; drop every sentence left without one. Returns (text, kept, dropped)."""
    segs = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    merged = []
    for s in segs:                              # "… fought. [#12]" -> the citation belongs to the sentence before
        if merged and not re.sub(r"[\s\[\]#\d,.;]", "", s):
            p = merged[-1]
            end = p[-1] if p[-1] in ".!?" else ""
            merged[-1] = p[:len(p) - len(end)] + " " + s.rstrip(".!? ") + end
        else:
            merged.append(s)
    out, dropped = [], 0
    for s in merged:
        s = re.sub(r"\[?#(\d+)\]?", lambda m: f"[#{m[1]}]" if int(m[1]) in ids else "", s)
        s = re.sub(r"\[\s*[,;]?\s*\]|\(\s*\)", "", s)
        s = re.sub(r"\s+([.,;!?])", r"\1", re.sub(r"\s{2,}", " ", s)).strip()
        s = re.sub(r"[,;]+(?=[.!?]|$)|,(?=,)", "", s)     # "[#16], ." left by a removed id
        if re.search(r"\[#\d+\]", s):
            out.append(s)
        else:
            dropped += 1
    return " ".join(out), len(out), dropped


SYSTEM = ("You are a security control-room assistant. Answer ONLY from the incident rows given (times are IST). "
          "Every sentence must cite the rows it uses as [#id], for example [#12]. Restate only what the rows say: no "
          "guesses about causes, injuries, people or outcomes. At most 3 short sentences, plain English, no lists.")


def _generate(messages, cancel, t0):
    """One streamed text call (D38: same num_ctx as vision). Returns (text or None if cancelled, first-token ms from t0)."""
    body = {"model": V["model"], "stream": True, "think": V["think"], "keep_alive": V["keep_alive"], "messages": messages,
            "options": {"temperature": 0, "num_predict": 150, "num_ctx": V["num_ctx"]}}
    text, ttft = "", None
    with httpx.stream("POST", V["base_url"] + V["endpoint"], json=body, timeout=MODEL_WAIT_S) as r:
        r.raise_for_status()
        for raw in r.iter_lines():
            if not raw:
                continue
            ch = json.loads(raw)
            if ch.get("error"):
                raise RuntimeError(ch["error"])
            if ttft is None:
                ttft = round((time.time() - t0) * 1000)
            text += ch.get("message", {}).get("content", "")
            if cancel.is_set():
                return None, ttft
            if ch.get("done") or time.time() - t0 > MODEL_WAIT_S:
                break
    return text, ttft


def ask_model(arb, messages, t0):
    """P2 call through the arbiter; a P1 that preempts it makes it retry (FR-8a). None if no answer by MODEL_WAIT_S."""
    while (left := t0 + MODEL_WAIT_S - time.time()) > 0:
        out, done = {}, threading.Event()

        def fn(req):
            try:
                out["r"] = _generate(messages, req["cancel"], t0)
            except Exception as e:              # the arbiter must never die on a chat call
                out["e"] = e
            finally:
                done.set()
        req = arb.submit({"prio": 2, "cam": "chat", "fn": fn})
        if not done.wait(left):
            arb.drop(req); req["cancel"].set()
            return None
        if "e" in out:
            print(f"[chat] model error: {out['e']!r}", flush=True)
            return None
        if out["r"][0] is not None:
            return out["r"]
    return None


def answer(question, db, arb, names=None, now=None):
    """POST /api/chat body -> §7.5 response (+ `how`: template, or model rows / sentences kept / dropped)."""
    t0 = time.time()
    now = now or t0
    names = cam_names(db, names)
    f = parse(question, names, now)
    rows, obs = retrieve(db, f)
    how = {"mode": "template"}
    if not rows:
        if f["event_id"] is not None:
            text = f"No event #{f['event_id']}."
        else:
            text = f"No matching events ({describe(f, names)})."
            if f["unknown_cameras"] or set(f["cameras"]) - set(names):
                bad = f["unknown_cameras"] + sorted(set(f["cameras"]) - set(names))
                text += f" No camera called {', '.join(bad)}; cameras: {', '.join(display(c, names) for c in names) or 'none'}."
            if obs:
                text += " Observations that mention it (not incidents): " + "; ".join(
                    f"{fmt(o['ts'])} {display(o['camera_id'], names)}: “{o['summary']}”" for o in obs) + "."
    elif f["intent"] == "summary":
        rows = rows[:LIMIT["summary"]]
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Question: {question}\nRows:\n" + "\n".join(
                    f"[#{e['id']}] {fmt(e['start_ts'])}, {display(e['camera_id'], names)}, {e['category'].replace('_', ' ')}: "
                    f"{e['summary'] or 'no summary'}" for e in sorted(rows, key=lambda e: e["start_ts"]))}]
        # oldest first (newest-first rows got the chronology wrong); no severity/confidence (the model misread them)
        r = ask_model(arb, msgs, t0)
        text, kept, dropped = ground(r[0], {e["id"] for e in rows}) if r else ("", 0, 0)
        how = {"mode": "model", "rows": len(rows), "sentences": kept, "dropped": dropped, "first_token_ms": r and r[1]}
        if not kept:                            # nothing survived (or no model in time): the template list
            f2 = f | {"intent": "list"}
            text = template(f2, rows, names) + ("" if r else "\n(model busy: listed instead)")
            how["fallback"] = "template list"
    else:
        total = None
        if f["intent"] == "list" and len(rows) == f["limit"]:
            total = len(retrieve(db, f | {"limit": 10000})[0])
        text = template(f, rows, names, total)
    ev = [e | {"camera_name": display(e["camera_id"], names)} for e in rows]
    return {"answer": text, "events": ev, "filters": f, "as_of": now, "latency_ms": round((time.time() - t0) * 1000),
            "how": how}


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from app.db import DB
    from scripts.seed_history import seed

    NOW = dt.datetime(2026, 10, 16, 6, 0, tzinfo=IST).timestamp()
    db = DB(Path(tempfile.mkdtemp()) / "c.db")
    seed(db, NOW)
    names = cam_names(db, {"cam1": "v011.avi"})
    P = lambda s: parse(s, names, NOW)
    h = lambda ts: dt.datetime.fromtimestamp(ts, IST).strftime("%d %H:%M")
    # 1. Rules: time (IST), cameras, categories, intents, keywords.
    f = P("What happened between 2 and 3 am?")
    assert f["intent"] == "summary" and (h(f["t_from"]), h(f["t_to"])) == ("16 02:00", "16 03:00"), f
    f = P("How many incidents in the last 10 minutes?")
    assert f["intent"] == "count" and f["t_to"] - f["t_from"] == 600 and not f["keywords"], f
    f = P("since 9 pm yesterday")
    assert (h(f["t_from"]), h(f["t_to"])) == ("15 21:00", "16 06:00"), (h(f["t_from"]), h(f["t_to"]))
    assert h(P("at 9 pm")["t_from"]) == "15 20:45"                       # a clock time still to come = yesterday's
    assert (h(P("between 10 pm and 2 am")["t_from"]), h(P("between 10 pm and 2 am")["t_to"])) == ("15 22:00", "16 02:00")
    assert h(P("this morning")["t_from"]) == "16 06:00" and h(P("yesterday")["t_to"]) == "16 00:00"
    f = P("Any tailgating in the lobby?")
    assert f["cameras"] == ["lobby"] and f["categories"] == ["tailgating"] and f["intent"] == "list" and not f["keywords"], f
    assert P("events on the parking lot")["cameras"] == ["parking_lot"] and P("camera 1")["cameras"] == ["cam1"]
    assert P("show v011")["cameras"] == ["cam1"]
    f = P("Any fights on the rooftop camera?")
    assert f["unknown_cameras"] == ["rooftop"] and f["categories"] == ["fighting"], f
    assert P("When was the last fire?")["intent"] == "latest" and P("tell me about event 15")["event_id"] == 15
    f = P("Find the man in the blue jacket")
    assert f["keywords"] == ["man", "blue", "jacket"] and f["intent"] == "list", f
    assert P("list theft")["subtypes"] == ["theft"] and P("fire or smoke")["subtypes"] == []
    # 2. Templates: every returned event cited, dismissed excluded, traps answered plainly.
    A = lambda s: answer(s, db, None, {"cam1": "v011.avi"}, NOW)
    cited = lambda r: {int(i) for i in re.findall(r"\[#(\d+)\]", r["answer"])}
    for q, ids in [("How many fights were there?", {7, 14, 16}), ("Show all events today", set(range(13, 24))),
                   ("Find the man in the blue jacket", {15, 16}), ("Details of #7", {7}), ("When was the last fire?", {18})]:
        r = A(q)
        assert {e["id"] for e in r["events"]} == ids == cited(r) and r["how"]["mode"] == "template", (q, r["answer"])
    for q in ("Any fights on the rooftop camera?", "What did the man in red do?", "Tell me about event 999",
              "Were there any fights in the server room?", "How many events on camera 9?"):
        r = A(q)
        assert r["events"] == [] and not cited(r) and r["answer"].startswith("No "), (q, r["answer"])
    assert "No camera called rooftop" in A("Any fights on the rooftop camera?")["answer"]
    assert "delivery van" in A("Show the delivery van")["answer"]       # observation fallback, quoted verbatim
    # 3. Sentence-level grounding (D57).
    t, k, d = ground("Two men fought [#7]. A third man joined [#99]. Nothing else happened. Smoke rose. [#18]", {7, 18})
    assert t == "Two men fought [#7]. Smoke rose [#18]." and (k, d) == (2, 2), (t, k, d)
    assert ground("All quiet tonight.", {1}) == ("", 0, 1)
    assert ground("Fights at [#7, #14].", {7, 14})[0] == "Fights at [#7], [#14]."
    # 4. Summary path with a fake model: invented id removed, uncited sentence dropped; all dropped -> template list.
    from app.models import Arbiter
    arb = Arbiter(lambda r: r["fn"](r)); arb.start()
    fake = {"text": "A man showed a knife [#15] and fought a guard [#16, #42]. Police arrived [#42]. It was calm."}
    _generate = lambda m, cancel, t0: (fake["text"], 5)
    r = answer("What happened between 2 and 3 am?", db, arb, None, NOW)
    assert r["answer"] == "A man showed a knife [#15] and fought a guard [#16]." and r["how"]["dropped"] == 2, r
    assert {e["id"] for e in r["events"]} == {15, 16, 17} and r["how"]["rows"] == 3
    fake["text"] = "Everything was fine."
    r = answer("Summarise the lobby today", db, arb, None, NOW)
    assert r["how"]["fallback"] == "template list" and cited(r) == {e["id"] for e in r["events"]} == {15, 16, 20, 23}, r
    # 5. A gate-triggered P1 preempts a running chat call; chat retries and still answers (FR-8a).
    calls = []

    def slow(m, cancel, t0):
        calls.append(1)
        for _ in range(30):
            if cancel.is_set():
                return None, 1
            time.sleep(0.01)
        return "The lobby had incidents [#20].", 1
    _generate = slow
    th = threading.Thread(target=lambda: fake.update(r=answer("Summarise the lobby today", db, arb, None, NOW)))
    th.start(); time.sleep(0.1)
    arb.submit({"prio": 1, "cam": "cam1", "fn": lambda req: time.sleep(0.05)})
    th.join(5)
    assert len(calls) == 2 and fake["r"]["answer"] == "The lobby had incidents [#20].", (calls, fake.get("r"))
    arb.stop()
    lat = [A(q)["latency_ms"] for q in ["Show all events today", "How many fights?", "Find the man in the blue jacket"] * 10]
    print(f"chat self-check ok: template latency max {max(lat)} ms")
