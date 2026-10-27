"""End-to-end check of every scenario through the API.

    python scripts/smoke_test.py          # mock models, no credits used
    python scripts/smoke_test.py --live   # real Token Factory calls (needs NEBIUS_API_KEY)
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if "--live" not in sys.argv:
    os.environ["MOCK_LLM"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

failures = 0


def check(cond, label):
    global failures
    print(("  ok   " if cond else "  FAIL ") + label)
    failures += not cond


def turn(c, sid, text="", action=None):
    events = []
    with c.stream("POST", "/api/turn", json={"session_id": sid, "text": text, "action": action}) as r:
        for line in r.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    errors = [e for e in events if e["type"] == "error"]
    if errors:
        print("  error event:", errors[0]["message"])
    return {e["type"]: e for e in events}


with TestClient(app) as c:
    print("models:", c.get("/api/health").json())

    print("salary: weak range ask, then accept")
    s = c.post("/api/session", json={"scenario_id": "salary", "difficulty": "tough"}).json()
    sid = s["session_id"]
    check("walk_away" not in json.dumps(s["scenario"]), "hidden hand not sent to browser")
    ev = turn(c, sid, "Sorry, is there any chance of maybe $74,000 to $78,000?")
    check("coach" in ev and "reply" in ev, "coach then reply streamed")
    if "coach" in ev:
        check(ev["coach"]["coach"]["anchoring"] <= 5, f"range ask scores weak anchoring ({ev['coach']['coach']['anchoring']})")
    offer = ev.get("reply", {}).get("state", {}).get("current", 0)
    check(72000 <= offer <= 84000, f"counter offer within limits ({offer})")
    ev = turn(c, sid, action="accept")
    check("closed" in ev, "accept closes the deal")
    if "closed" in ev:
        rv = ev["closed"]["reveal"]
        check(rv["walk_away"] == 84000 and rv["left_on_table"] == 84000 - rv["result"], f"reveal math ({rv['left_on_table']} left)")
    d = c.post("/api/debrief", json={"session_id": sid}).json()
    check(bool(d.get("debrief", {}).get("headline")), "debrief generated")
    r = c.post("/api/replay", json={"session_id": sid, "turn": 1}).json()
    check(len(r["messages"]) == 1 and not r["state"]["closed"], "replay from turn 1 restores the opening")
    ev = turn(c, sid, "I have a competing offer at $86,000, so I need $84,000 because that's the market rate.")
    check("reply" in ev, "strong turn after replay works")

    print("deposit: hardball until the end")
    sid = c.post("/api/session", json={"scenario_id": "deposit", "difficulty": "hardball"}).json()["session_id"]
    for i in range(12):
        ev = turn(c, sid, "I'd like more back please?")
        if i == 0:
            check("closed" not in ev, "a vague ask doesn't end the negotiation")
        if "closed" in ev:
            break
    check("closed" in ev, f"hardball ends within {i + 1} turns ({ev.get('closed', {}).get('reveal', {}).get('outcome')})")
    rv = ev.get("closed", {}).get("reveal", {})
    check(rv.get("best_offer", 0) <= 1650, "never exceeds the walk-away")

    print("aid: walk-away threat triggers a final offer")
    sid = c.post("/api/session", json={"scenario_id": "aid", "difficulty": "friendly"}).json()["session_id"]
    ev = turn(c, sid, action="walk")
    check(ev.get("reply", {}).get("state", {}).get("final_made"), "emergency final offer made")
    ev = turn(c, sid, action="walk")
    check(ev.get("closed", {}).get("reveal", {}).get("outcome") == "user_walked", "second walk ends it")

    print("scam: questions, then hang up")
    sid = c.post("/api/session", json={"scenario_id": "scam", "difficulty": "tough"}).json()["session_id"]
    ev = turn(c, sid, "Why is this so urgent? What's your middle name?")
    check("reply" in ev, "scammer replies")
    ev = turn(c, sid, "I'm going to hang up and call your mother.")
    rv = ev.get("closed", {}).get("reveal", {})
    check(rv.get("outcome") == "safe", "hanging up is safe")
    check(any(f["used"] for f in rv.get("red_flags", [])), "red flags tracked")

    print("custom scenario")
    s = c.post("/api/session", json={"scenario_id": "custom", "difficulty": "tough",
                                     "situation": "I'm a freelance designer and a startup offered $2,000 for a logo package."}).json()
    check(s.get("scenario", {}).get("type") == "money" and len(s["calls"]) >= 1, "custom hand generated")

print("\nFAILED" if failures else "\nALL PASSED", f"({failures} failures)")
sys.exit(1 if failures else 0)
