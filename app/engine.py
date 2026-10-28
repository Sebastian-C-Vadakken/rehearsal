"""Deal engine: hidden hands, turn logic, replay, reveal and debrief.

Model routing per user turn:
  Nano  -> scores the user's message (coach meters + signals like the amount asked for)
  Python -> turns Nano's read into leverage, decides what the counterpart is ALLOWED to offer
  Ultra -> plays the counterpart inside those limits (it never sees the walk-away number)
"""

import copy
import json
import math
import re
import time
import uuid
from collections import OrderedDict
from pathlib import Path

from . import config, llm, prompts
from .prompts import money

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"

# step: share of the (walk_away - opening) gap the counterpart can concede per turn at 1.0x leverage
DIFFICULTY = {
    "friendly": {"step": 0.30, "patience": 7, "they_walk": False},
    "tough": {"step": 0.18, "patience": 5, "they_walk": False},
    "hardball": {"step": 0.11, "patience": 4, "they_walk": True},
}
# How many resistant replies the scammer tolerates before giving up.
SCAM_PATIENCE = {"friendly": 5, "tough": 7, "hardball": 9}

ACTION_TEXT = {
    "accept": "I accept your offer.",
    "walk": "I'm going to walk away from this.",
    "hangup": "(You hang up the phone.)",
}

PUBLIC_FIELDS = ("id", "type", "title", "blurb", "audience", "user_role", "counterpart_name",
                 "counterpart_role", "value_label", "opening", "amount", "red_flags")


class EngineError(RuntimeError):
    pass


def load_scenarios() -> dict[str, dict]:
    items = [json.loads(p.read_text(encoding="utf-8")) for p in SCENARIO_DIR.glob("*.json")]
    return {s["id"]: s for s in sorted(items, key=lambda s: s.get("order", 99))}


SCENARIOS = load_scenarios()


def public_scenario(s: dict) -> dict:
    pub = {k: s[k] for k in PUBLIC_FIELDS if k in s}
    if "red_flags" in pub:  # labels are revealed only at the end
        pub["red_flags"] = len(pub["red_flags"])
    return pub


def _score(v) -> int:
    try:
        return max(0, min(10, round(float(v))))
    except (TypeError, ValueError):
        return 0


def _amount(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    text = str(v).lower().replace(",", "").replace("$", "").strip()
    mult = 1000 if text.endswith("k") else 1
    try:
        n = float(text.rstrip("k")) * mult
    except ValueError:
        return None
    return n if n > 0 else None


def _bool(v) -> bool:
    return v is True or (isinstance(v, str) and v.strip().lower() == "true")


def nice_increment(value: float) -> int:
    for inc in (5000, 2500, 1000, 500, 250, 100, 50, 25, 10, 5, 1):
        if inc <= value * 0.006:
            return inc
    return 1


def leverage(coach: dict) -> float:
    """0.3x (weak, apologetic, no ask) .. 1.7x (specific anchor, confident, justified)."""
    raw = (coach["anchoring"] + coach["confidence"] + coach["justification"] + 0.5 * coach["info_gathering"]) / 35
    return round(0.3 + 1.4 * min(1.0, raw), 2)


class Session:
    def __init__(self, scenario: dict, difficulty: str, calls: list | None = None):
        if difficulty not in DIFFICULTY:
            raise EngineError(f"unknown difficulty {difficulty}")
        self.id = uuid.uuid4().hex
        self.s = scenario
        self.difficulty = difficulty
        self.created = time.time()
        self.calls: list[dict] = calls if calls is not None else []  # never rewound: replays still cost tokens
        self.debrief: dict | None = None
        self.coach: list[dict] = []
        self.snapshots: list = []
        if scenario["type"] == "money":
            opening_raw = {"reply": scenario["opening_line"], "offer": scenario["opening"], "tactic": "none"}
            self.state = {"turn": 0, "closed": False, "outcome": None, "result": None,
                          "current": scenario["opening"], "patience": DIFFICULTY[difficulty]["patience"],
                          "final_made": False, "final_pushes": 0}
        else:
            opening_raw = {"reply": scenario["opening_line"], "tactic": "emotion"}
            self.state = {"turn": 0, "closed": False, "outcome": None, "patience": SCAM_PATIENCE[difficulty],
                          "used": ["emotion"], "called_out": [], "shared": 0}
        self.messages = [{"role": "them", "text": scenario["opening_line"], "turn": 0,
                          "raw": json.dumps(opening_raw), "offer": scenario.get("opening")}]

    # ---------- public views ----------

    def public_state(self) -> dict:
        st = self.state
        out = {"turn": st["turn"], "closed": st["closed"], "outcome": st["outcome"]}
        if self.s["type"] == "money":
            out.update(current=st["current"], final_made=st["final_made"])
        return out

    def snapshot_view(self) -> dict:
        return {"session_id": self.id, "scenario": public_scenario(self.s), "difficulty": self.difficulty,
                "messages": [self._msg_view(m) for m in self.messages], "coach": self.coach,
                "state": self.public_state(), "calls": self.calls,
                "reveal": self.reveal() if self.state["closed"] else None}

    @staticmethod
    def _msg_view(m: dict) -> dict:
        return {k: v for k, v in m.items() if k != "raw"}

    # ---------- turns ----------

    async def turn(self, text: str, action: str | None):
        """Async generator of UI events. Rolls back the turn if a model call fails."""
        if self.state["closed"]:
            raise EngineError("This negotiation is over. Replay a turn or start again.")
        text = (text or "").strip()[:1000]
        if not text and action not in ACTION_TEXT:
            raise EngineError("Say something first.")
        if text and self.state["turn"] >= config.MAX_TURNS:
            end = "hang up" if self.s["type"] == "scam" else "accept or walk away"
            raise EngineError(f"That's the turn limit for one round. You can {end}, or replay from an earlier turn.")
        if len(self.calls) >= config.MAX_SESSION_CALLS:
            raise EngineError("This session has used its share of the demo. Start a new scenario to keep practising.")
        self.snapshots.append(copy.deepcopy((self.messages, self.coach, self.state)))
        self.state["turn"] += 1
        n = self.state["turn"]
        self.messages.append({"role": "user", "text": text or ACTION_TEXT[action], "turn": n,
                              "action": None if text else action})
        try:
            gen = self._money_turn(n, text, action) if self.s["type"] == "money" else self._scam_turn(n, text, action)
            async for ev in gen:
                yield ev
        except llm.LLMError:
            self.messages, self.coach, self.state = self.snapshots.pop()
            raise

    def _their_last_line(self) -> str:
        return next(m["text"] for m in reversed(self.messages) if m["role"] == "them")

    def _history(self, engine_note: str) -> list[dict]:
        msgs = []
        for m in self.messages:
            if m["role"] == "them":
                msgs.append({"role": "assistant", "content": m["raw"]})
            else:
                msgs.append({"role": "user", "content": m["text"]})
        msgs[-1] = {"role": "user", "content": f"{msgs[-1]['content']}\n\n{engine_note}"}
        return msgs

    def _close(self, outcome: str, result=None):
        self.state.update(closed=True, outcome=outcome)
        if self.s["type"] == "money":
            self.state["result"] = result

    async def _money_turn(self, n: int, text: str, action: str | None):
        s, st, d = self.s, self.state, DIFFICULTY[self.difficulty]
        cur, walk, inc = st["current"], s["walk_away"], s["increment"]
        span = walk - s["opening"]
        lev = None

        if action:
            accepts, walks, ask = action == "accept", action == "walk", None
        else:
            coach = await self._coach_money(text, cur)
            lev = leverage(coach)
            coach["leverage"] = lev
            self.coach.append({"turn": n, **coach})
            yield {"type": "coach", "turn": n, "coach": coach}
            accepts, walks, ask = coach["accepts"], coach["walks"], coach["user_ask"]
            # Nano sometimes invents an amount for vague asks ("can you do better?"); only trust stated numbers.
            if ask is not None and (ask <= cur or not re.search(r"\d", text)):
                ask = coach["user_ask"] = None

        def floor_inc(v):
            return max(cur, math.floor(v / inc) * inc)

        close = None
        if accepts:
            key, x, low, high, close = "accepted", cur, cur, cur, ("deal", cur)
        elif walks and st["final_made"]:
            key, x, low, high, close = "they_walk", cur, cur, cur, ("user_walked", None)
        elif walks:
            x = floor_inc(min(walk, cur + span * d["step"] * 2))
            key, low, high = "emergency", x, x
            st["final_made"] = True
        else:
            cap = floor_inc(min(walk, cur + span * d["step"] * lev))
            if ask is not None and ask <= cap:
                key, x, low, high, close = "accept_ask", ask, ask, ask, ("deal", ask)
            elif st["final_made"] and d["they_walk"]:
                key, x, low, high, close = "they_walk", cur, cur, cur, ("they_walked", None)
            elif st["final_made"]:
                st["final_pushes"] += 1
                key, x, low, high = "hold", cur, cur, cur
                if st["final_pushes"] >= 2:
                    close = ("final_stood", cur)
            else:
                st["patience"] -= 1
                if st["patience"] <= 0:
                    key, x, low, high = "final", cap, cap, cap
                    st["final_made"] = True
                else:
                    key, x, low, high = "counter", cap, cur, cap

        note = prompts.engine_note_money(cur, low, high, prompts.DIRECTIVES[key].format(x=money(x)))

        def validate(data):
            offer = _amount(data.get("offer"))
            if not isinstance(data.get("reply"), str) or not data["reply"].strip():
                raise ValueError("missing reply")
            if offer is None or not (low - 0.5 <= offer <= high + 0.5):
                raise ValueError(f"offer must be between {money(low)} and {money(high)}")
            data["offer"] = round(offer)

        reply = await llm.chat_json("ultra", "counterpart", [
            {"role": "system", "content": prompts.counterpart_money_system(s, self.difficulty)},
            *self._history(note)], self.calls, validate=validate)
        st["current"] = reply["offer"]
        msg = {"role": "them", "text": reply["reply"].strip(), "turn": n, "offer": reply["offer"],
               "tactic": str(reply.get("tactic") or "none"), "raw": json.dumps(reply)}
        self.messages.append(msg)
        yield {"type": "reply", "message": self._msg_view(msg), "state": self.public_state(),
               "engine": {"leverage": lev, "directive": key}}
        if close:
            self._close(*close)
            yield {"type": "closed", "state": self.public_state(), "reveal": self.reveal()}

    async def _coach_money(self, text: str, cur: float) -> dict:
        def validate(data):
            for k in ("anchoring", "confidence", "justification", "info_gathering"):
                data[k] = _score(data.get(k))
            data["user_ask"] = _amount(data.get("user_ask"))
            data["accepts"], data["walks"] = _bool(data.get("accepts")), _bool(data.get("walks"))
            if _bool(data.pop("gave_range", False)):  # a range invites them to pay the bottom of it
                data["anchoring"] = min(data["anchoring"], 2)
            data["tip"] = str(data.get("tip") or "")[:160]

        return await llm.chat_json_hedged("nano", "super", "coach", [
            {"role": "system", "content": prompts.COACH_MONEY_SYSTEM.format(value_label=self.s["value_label"])},
            {"role": "user", "content": prompts.coach_money_user(cur, self._their_last_line(), text)},
        ], self.calls, max_tokens=400, temperature=0.2, validate=validate, thinking=False)

    async def _scam_turn(self, n: int, text: str, action: str | None):
        s, st = self.s, self.state
        flags = {f["id"]: f for f in s["red_flags"]}

        if action == "hangup":
            self._close("safe")
            yield {"type": "closed", "state": self.public_state(), "reveal": self.reveal()}
            return

        def validate(data):
            for k in ("skepticism", "verification", "info_protection"):
                data[k] = _score(data.get(k))
            for k in ("agreed_to_pay", "shared_sensitive", "hangs_up"):
                data[k] = _bool(data.get(k))
            called = data.get("called_out") or []
            data["called_out"] = [c for c in called if isinstance(c, str) and c in flags]
            data["tip"] = str(data.get("tip") or "")[:160]

        coach = await llm.chat_json_hedged("nano", "super", "coach", [
            {"role": "system", "content": prompts.coach_scam_system(s["red_flags"])},
            {"role": "user", "content": prompts.coach_scam_user(self._their_last_line(), text)},
        ], self.calls, max_tokens=400, temperature=0.2, validate=validate, thinking=False)
        self.coach.append({"turn": n, **coach})
        yield {"type": "coach", "turn": n, "coach": coach}

        st["called_out"] = sorted(set(st["called_out"]) | set(coach["called_out"]))
        st["shared"] += int(coach["shared_sensitive"])
        if coach["agreed_to_pay"]:
            self._close("scammed")
        elif coach["hangs_up"]:
            self._close("safe")
        if st["closed"]:
            yield {"type": "closed", "state": self.public_state(), "reveal": self.reveal()}
            return

        resisted = coach["verification"] >= 6 or coach["skepticism"] >= 7
        st["patience"] -= 2 if resisted else 1
        flag = None
        if st["patience"] > 0:
            unused = [f for f in s["red_flags"] if f["id"] not in st["used"]]
            flag = unused[0] if unused else s["red_flags"][n % len(s["red_flags"])]

        def validate_reply(data):
            if not isinstance(data.get("reply"), str) or not data["reply"].strip():
                raise ValueError("missing reply")
            if data.get("tactic") not in flags:
                data["tactic"] = flag["id"] if flag else "none"

        reply = await llm.chat_json("ultra", "counterpart", [
            {"role": "system", "content": prompts.counterpart_scam_system(s, self.difficulty)},
            *self._history(prompts.engine_note_scam(flag))], self.calls, validate=validate_reply)
        if reply["tactic"] in flags and reply["tactic"] not in st["used"]:
            st["used"].append(reply["tactic"])
        msg = {"role": "them", "text": reply["reply"].strip(), "turn": n, "tactic": reply["tactic"],
               "raw": json.dumps(reply)}
        self.messages.append(msg)
        yield {"type": "reply", "message": self._msg_view(msg), "state": self.public_state(), "engine": None}
        if flag is None:
            self._close("safe")
            yield {"type": "closed", "state": self.public_state(), "reveal": self.reveal()}

    # ---------- replay / reveal / debrief ----------

    def replay(self, turn: int) -> dict:
        if not 1 <= turn <= len(self.snapshots):
            raise EngineError("No such turn to replay from.")
        self.messages, self.coach, self.state = copy.deepcopy(self.snapshots[turn - 1])
        del self.snapshots[turn - 1:]
        self.debrief = None
        return self.snapshot_view()

    def reveal(self) -> dict:
        s, st = self.s, self.state
        if s["type"] == "money":
            walk, opening, result = s["walk_away"], s["opening"], st["result"]
            got = result if result is not None else st["current"]
            span = walk - opening
            return {"type": "money", "outcome": st["outcome"], "result": result, "best_offer": st["current"],
                    "opening": opening, "walk_away": walk, "left_on_table": max(0, walk - got),
                    "captured_pct": round(100 * (got - opening) / span) if span else 100,
                    "value_label": s["value_label"], "hidden_story": s["hidden_story"]}
        return {"type": "scam", "outcome": st["outcome"], "amount": s["amount"], "shared": st["shared"],
                "turns": st["turn"], "hidden_story": s["hidden_story"],
                "red_flags": [{**f, "used": f["id"] in st["used"], "spotted": f["id"] in st["called_out"]}
                              for f in s["red_flags"]]}

    async def make_debrief(self) -> dict:
        if not self.state["closed"]:
            raise EngineError("Finish the negotiation first.")
        if self.debrief:
            return self.debrief
        n_turns = self.state["turn"]
        coach_by_turn = {c["turn"]: c for c in self.coach}
        lines = []
        for m in self.messages:
            if m["role"] == "user":
                c = coach_by_turn.get(m["turn"])
                scores = ""
                if c:
                    keys = [k for k in c if isinstance(c[k], int) and k != "turn" and not isinstance(c[k], bool)]
                    scores = "  [coach: " + ", ".join(f"{k}={c[k]}" for k in keys) + "]"
                lines.append(f"T{m['turn']} USER: {m['text']}{scores}")
            else:
                offer = f"  [offer now {money(m['offer'])}]" if m.get("offer") is not None else ""
                tactic = f"  [tactic: {m['tactic']}]" if m.get("tactic") not in (None, "none") else ""
                lines.append(f"THEM: {m['text']}{offer}{tactic}")
        rv = self.reveal()
        if rv["type"] == "money":
            final = money(rv["result"]) if rv["result"] is not None else "no deal"
            hidden = (f"Hidden hand: opening {money(rv['opening'])}, walk-away (their true max) {money(rv['walk_away'])}. "
                      f"{rv['hidden_story']}\nOutcome: {rv['outcome']}, final {final}, "
                      f"{money(rv['left_on_table'])} left on the table ({rv['captured_pct']}% of the available room captured).")
            kind = "negotiation coach"
        else:
            flags = "; ".join(f"{f['id']} (used={f['used']}, spotted={f['spotted']})" for f in rv["red_flags"])
            hidden = (f"It was a scam. {rv['hidden_story']}\nOutcome: {rv['outcome']}. "
                      f"Times the user shared sensitive info: {rv['shared']}. Red flags: {flags}")
            kind = "fraud-prevention coach"

        def validate(data):
            if not isinstance(data.get("headline"), str):
                raise ValueError("missing headline")
            anns = [a for a in data.get("annotations") or [] if isinstance(a, dict)]
            for a in anns:
                try:
                    a["turn"] = int(a.get("turn"))
                except (TypeError, ValueError):
                    a["turn"] = 0
                a["verdict"] = a.get("verdict") if a.get("verdict") in ("strong", "ok", "mistake") else "ok"
            data["annotations"] = [a for a in anns if 1 <= a["turn"] <= n_turns]
            tp = data.get("turning_point")
            data["turning_point"] = tp if isinstance(tp, int) and 1 <= tp <= n_turns else None
            data["lessons"] = [str(x) for x in (data.get("lessons") or [])][:3]

        self.debrief = await llm.chat_json("ultra", "debrief", [
            {"role": "system", "content": prompts.DEBRIEF_SYSTEM.format(coach_kind=kind)},
            {"role": "user", "content": f"Scenario: {self.s['title']} ({self.difficulty}).\n{hidden}\n\nTranscript:\n" + "\n".join(lines)},
        ], self.calls, max_tokens=2500, temperature=0.4, validate=validate)
        return self.debrief


async def build_custom_scenario(situation: str, calls: list) -> dict:
    situation = situation.strip()[:2000]
    if len(situation) < 20:
        raise EngineError("Describe your situation in a sentence or two.")

    def validate(data):
        for k in ("title", "user_role", "counterpart_name", "counterpart_role", "context",
                  "persona_secret", "value_label", "opening_line", "hidden_story"):
            if not isinstance(data.get(k), str) or not data[k].strip():
                raise ValueError(f"missing {k}")
        opening, walk = _amount(data.get("opening")) or 0, _amount(data.get("walk_away"))
        if walk is None or walk <= opening:
            raise ValueError("walk_away must be a number greater than opening")
        if opening and walk > opening * 2.5:
            raise ValueError("walk_away is unrealistically far above opening")
        data["opening"], data["walk_away"] = round(opening), round(walk)
        data["tactics"] = [str(t) for t in (data.get("tactics") or [])][:5] or ["hold firm and ask for reasons"]

    hand = await llm.chat_json("ultra", "custom_scenario", [
        {"role": "system", "content": prompts.CUSTOM_HAND_SYSTEM},
        {"role": "user", "content": situation},
    ], calls, max_tokens=1500, temperature=0.5, validate=validate)
    inc = nice_increment(hand["walk_away"])
    hand["walk_away"] = max(hand["opening"] + inc, math.floor(hand["walk_away"] / inc) * inc)
    return {**hand, "id": "custom", "type": "money", "increment": inc,
            "blurb": "Your own situation, with a hidden hand built from it.", "audience": "You"}


class SessionStore:
    def __init__(self):
        self._items: OrderedDict[str, Session] = OrderedDict()

    def add(self, session: Session):
        self._items[session.id] = session
        while len(self._items) > config.MAX_SESSIONS:
            self._items.popitem(last=False)

    def get(self, sid: str) -> Session:
        try:
            return self._items[sid]
        except KeyError:
            raise EngineError("Session expired. Start a new one.") from None
