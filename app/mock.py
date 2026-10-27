"""Canned model replies for MOCK_LLM=1 (UI development without spending credits)."""

import asyncio
import json
import re

DELAY = {"coach": 0.4, "counterpart": 1.2, "debrief": 1.5, "custom_scenario": 1.5}


def _amounts(text: str) -> list[float]:
    out = []
    for num, k in re.findall(r"\$?(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", text.lower()):
        v = float(num.replace(",", "")) * (1000 if k else 1)
        if v >= 100:
            out.append(v)
    return out


def _coach(msgs) -> dict:
    system, user = msgs[0]["content"], msgs[-1]["content"]
    said = user.rsplit("message:", 1)[-1] if "message:" in user else user.rsplit("reply:", 1)[-1]
    low = said.lower()
    if "fraud-prevention" in system:
        return {"skepticism": 8 if "?" in said else 3, "verification": 8 if "call" in low else 2,
                "info_protection": 9, "agreed_to_pay": "i'll send" in low or "okay i will" in low,
                "shared_sensitive": "my address" in low, "hangs_up": "hang up" in low or "goodbye" in low,
                "called_out": ["urgency"] if "rush" in low or "urgent" in low else [],
                "tip": "Ask a question only the real Jake would know."}
    amounts = _amounts(said)
    ranged = len(amounts) >= 2
    hedging = any(w in low for w in ("sorry", "maybe", "if possible", "i guess"))
    return {"anchoring": 2 if ranged else (8 if amounts else 1), "confidence": 3 if hedging else 7,
            "justification": 8 if any(w in low for w in ("offer", "market", "because", "law")) else 2,
            "info_gathering": 6 if "?" in said else 1, "user_ask": min(amounts) if amounts else None,
            "accepts": any(w in low for w in ("i accept", "deal", "sounds good")),
            "walks": "walk away" in low or "i decline" in low,
            "tip": "Name one specific number and give a reason." if not amounts else "Hold your number. Let them counter."}


def _counterpart(msgs) -> dict:
    note = msgs[-1]["content"]
    m = re.search(r"between \$([\d,]+) and \$([\d,]+)", note)
    if m:
        low, high = (float(x.replace(",", "")) for x in m.groups())
        offer = round((low + high) / 2) if high > low else low
        return {"reply": f"Let me see what I can do... I could move to ${offer:,.0f}.", "offer": offer, "tactic": "anchor"}
    tactic = re.search(r"tactic now: (\w+)", note)
    if tactic:
        return {"reply": "Please, Grandma, there's no time! They said I need the money today.", "tactic": tactic.group(1)}
    return {"reply": "I... I have to go. Bye.", "tactic": "none"}


def _debrief(msgs) -> dict:
    turns = sorted({int(t) for t in re.findall(r"^T(\d+) USER", msgs[-1]["content"], re.M)})
    return {"headline": "Mock debrief: you held your ground but asked too softly at first.",
            "turning_point": turns[0] if turns else None,
            "annotations": [{"turn": t, "verdict": "mistake" if t == turns[0] else "ok",
                             "note": "Mock note about this turn.", "better_line": "Mock better line."} for t in turns],
            "lessons": ["Anchor with one number.", "Give a reason.", "Let silence work."]}


def _custom(msgs) -> dict:
    return {"title": "Freelance rate negotiation", "user_role": "a freelance designer", "counterpart_name": "Sam",
            "counterpart_role": "a startup founder", "context": "Sam wants a logo package and offers $2,000.",
            "persona_secret": "Your launch is in two weeks and your last designer quit.",
            "tactics": ["say budget is fixed", "promise future work", "compare to cheaper marketplaces"],
            "opening": 2000, "walk_away": 2600, "value_label": "project fee",
            "opening_line": "We can do $2,000 for the full logo package. That's our budget.",
            "hidden_story": "Sam's launch was in two weeks and could pay up to $2,600."}


async def respond(purpose: str, msgs: list[dict]) -> str:
    await asyncio.sleep(DELAY.get(purpose, 0.5))
    fn = {"coach": _coach, "counterpart": _counterpart, "debrief": _debrief, "custom_scenario": _custom}[purpose]
    return json.dumps(fn(msgs))
