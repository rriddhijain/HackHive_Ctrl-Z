"""Chat question runner (P4 gate): bench/chat_questions.csv against the seeded history in a temp DB, now = 06:00 IST.

  uv run python -m bench.chat_runner          -> bench/results/chat_runner.csv + chat_runner_summary.json

Per question: right/wrong (intent matches, the events returned are exactly the expected ids, template answers cite
every one of them, model answers cite only them), intent, latency, first token (summary), invented events (cited ids
not among the returned events), uncited sentences in model-written text. Summary questions call the real model
through the arbiter at P2, with no camera running.
"""
import csv
import datetime as dt
import json
import re
import tempfile
from pathlib import Path

from app.chat import IST, answer
from app.config import ROOT
from app.db import DB
from app.models import Arbiter
from app.pipeline import pct
from scripts.seed_history import seed

NOW = dt.datetime(2026, 10, 16, 6, 0, tzinfo=IST).timestamp()
OUT = ROOT / "bench" / "results"


def main():
    db = DB(Path(tempfile.mkdtemp()) / "chat.db")
    seed(db, NOW)
    arb = Arbiter(lambda r: r["fn"](r)); arb.start()
    rows = []
    for q in csv.DictReader(open(ROOT / "bench" / "chat_questions.csv")):
        r = answer(q["question"], db, arb, {}, NOW)
        want = set() if q["ids"] == "none" else {int(i) for i in q["ids"].split()}
        got = {e["id"] for e in r["events"]}
        cited = {int(i) for i in re.findall(r"\[#(\d+)\]", r["answer"])}
        how = r["how"]
        model_text = how["mode"] == "model" and not how.get("fallback")
        uncited = sum(1 for s in re.split(r"(?<=[.!?])\s+", r["answer"].strip()) if s and not re.search(r"\[#\d+\]", s)) \
            if model_text else 0
        ok = r["filters"]["intent"] == q["intent"] and got == want and (cited <= got if model_text else cited == got)
        rows.append({"question": q["question"], "covers": q["covers"], "right": int(ok), "intent": r["filters"]["intent"],
                     "expected_intent": q["intent"], "expected_ids": q["ids"], "got_ids": " ".join(map(str, sorted(got))) or "none",
                     "invented": len(cited - got), "uncited": uncited, "latency_ms": r["latency_ms"],
                     "first_token_ms": how.get("first_token_ms"), "how": json.dumps(how), "answer": r["answer"]})
        print(f"{'OK ' if ok else 'BAD'} {r['filters']['intent']:8} {r['latency_ms']:5} ms  {q['question']}\n    {r['answer'][:300]}")
    arb.stop()
    OUT.mkdir(exist_ok=True)
    with open(OUT / "chat_runner.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    lat = lambda intent: [x["latency_ms"] for x in rows if x["intent"] == intent]
    tmpl = [x["latency_ms"] for x in rows if json.loads(x["how"])["mode"] == "template"]
    summ = {"right": sum(x["right"] for x in rows), "n": len(rows), "invented": sum(x["invented"] for x in rows),
            "uncited": sum(x["uncited"] for x in rows), "template_p50_ms": pct(tmpl, .5), "template_p95_ms": pct(tmpl, .95),
            "latency_by_intent_ms": {i: {"p50": pct(lat(i), .5), "max": max(lat(i))} for i in
                                     ("list", "count", "latest", "detail", "summary") if lat(i)},
            "summary_first_token_ms": [x["first_token_ms"] for x in rows if x["first_token_ms"]],
            "model_sentences_dropped": sum(json.loads(x["how"]).get("dropped", 0) for x in rows),
            "template_fallbacks": sum("fallback" in json.loads(x["how"]) for x in rows)}
    (OUT / "chat_runner_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    assert summ["invented"] == 0 and summ["uncited"] == 0, "grounding broken"


if __name__ == "__main__":
    main()
