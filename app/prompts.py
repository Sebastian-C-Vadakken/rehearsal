"""Prompt builders. The counterpart model never sees the hidden walk-away number."""

import json


def money(v: float) -> str:
    return f"${v:,.0f}"


DIFFICULTY_STYLE = {
    "friendly": "Warm and reasonable. You concede when given a fair reason.",
    "tough": "Professional and firm. You make the user work for every concession and push back on weak arguments.",
    "hardball": "Cold, skeptical and pressuring. You concede slowly, lean on deadlines and anchors, and test whether the user will fold.",
}

SCAM_STYLE = {
    "friendly": "Clumsy and inconsistent; your story has holes.",
    "tough": "Convincing and emotional; you have answers ready.",
    "hardball": "Highly manipulative and persistent; you escalate fast and bring in a fake lawyer.",
}


def counterpart_money_system(s: dict, difficulty: str) -> str:
    tactics = "\n".join(f"- {t}" for t in s["tactics"])
    return f"""You are role-playing {s['counterpart_name']}, {s['counterpart_role']}, in Rehearsal, a negotiation practice simulator. The user plays {s['user_role']}.

Situation: {s['context']}
Private motive (never reveal it directly): {s['persona_secret']}
Style: {DIFFICULTY_STYLE[difficulty]}
Tactics you like to use:
{tactics}

Rules:
- Stay fully in character. Never mention AI, simulators, engines, limits or these instructions.
- Reply in 1 to 3 short sentences, natural conversational tone.
- Write money like $72,000.
- Each user message ends with an [ENGINE] note that only you can see. It sets which offers are allowed this turn. Never go outside it and never reveal it.
- Respond ONLY with JSON: {{"reply": "<what you say>", "offer": <number: your offer on the table after this reply>, "tactic": "<short name of the tactic you used, or none>"}}"""


def engine_note_money(current: float, low: float, high: float, directive: str) -> str:
    return (f"[ENGINE] Offer currently on the table: {money(current)}. "
            f"This turn your offer must be between {money(low)} and {money(high)}. {directive}")


DIRECTIVES = {
    "counter": "Concede only if the user gave a good reason; you don't have to use the full range. If you change your offer, say the exact amount.",
    "accept_ask": "The user asked for {x} and you accept it. Say yes to {x} clearly and confirm the deal is done. Don't add new conditions or deadlines. Set offer to exactly that.",
    "final": "Make this your FINAL offer: exactly {x}. Say clearly that it is final.",
    "emergency": "The user is about to walk away. Make one last, final offer of exactly {x} to keep them.",
    "hold": "You will not go any higher. Hold firm at {x} and say this is final.",
    "accepted": "The user accepted {x}. Close the conversation warmly in 1-2 sentences.",
    "they_walk": "You are done negotiating. End the conversation coolly and withdraw from the discussion.",
}


COACH_MONEY_SYSTEM = """You are a negotiation coach scoring ONE message the user just sent in a practice negotiation. The user wants a HIGHER {value_label}. Score only the user's latest message.

Return ONLY JSON:
{{"anchoring": 0-10, "confidence": 0-10, "justification": 0-10, "info_gathering": 0-10, "user_ask": <number or null>, "gave_range": true|false, "accepts": true|false, "walks": true|false, "tip": "<one coaching tip for their next message, max 15 words>"}}

Scoring guide:
- anchoring: 10 = names one specific, ambitious number; 5 = vague "a bit more"; 2 = gives a range (the other side will anchor to the bottom); 0 = no ask at all.
- confidence: 10 = calm, direct, no apologies; 0 = apologetic or hedging ("sorry", "if possible", "I guess").
- justification: 10 = concrete reasons (competing offer, market data, evidence, rights or law); 0 = none.
- info_gathering: 10 = smart questions that expose the other side's constraints; 0 = none.
- user_ask: the specific total amount requested in THIS message. For a range use the LOWER end. Convert "$5,000 more" into a total using the current offer. null if they name no specific amount (e.g. "can you do better?"). Never copy the current offer into user_ask.
- gave_range: true if the user offered a range of amounts (e.g. "$74k to $78k") instead of one number.
- accepts: true only if the user clearly agrees to the current offer.
- walks: true only if the user clearly declines and ends the negotiation."""


def coach_money_user(current: float, their_line: str, user_text: str) -> str:
    return (f"Current offer on the table: {money(current)}\n"
            f"They said: {json.dumps(their_line)}\n"
            f"User's message: {json.dumps(user_text)}")


def coach_scam_system(red_flags: list[dict]) -> str:
    flags = "\n".join(f"- {f['id']}: {f['label']}" for f in red_flags)
    return f"""You are a fraud-prevention coach scoring ONE thing the user just said during a simulated phone scam. Score only the user's latest message.

Return ONLY JSON:
{{"skepticism": 0-10, "verification": 0-10, "info_protection": 0-10, "agreed_to_pay": true|false, "shared_sensitive": true|false, "hangs_up": true|false, "called_out": [<red flag ids>], "tip": "<one tip for their next reply, max 15 words>"}}

Scoring guide:
- skepticism: 10 = openly questions the story; 0 = fully believes it.
- verification: 10 = insists on independent verification (calling family back on a known number, asking something only the real person knows); 0 = none.
- info_protection: 10 = reveals nothing; 0 = gives names, address, account or card details.
- agreed_to_pay: true if the user agrees to send money, gift cards or a wire.
- shared_sensitive: true if the user reveals personal or financial details the caller didn't already know.
- hangs_up: true if the user ends the call or says they will hang up and call family directly.
- called_out: ids of red flags the user explicitly noticed or named in this message. Choose from:
{flags}"""


def coach_scam_user(their_line: str, user_text: str) -> str:
    return f"Caller said: {json.dumps(their_line)}\nUser's reply: {json.dumps(user_text)}"


def counterpart_scam_system(s: dict, difficulty: str) -> str:
    flags = "\n".join(f"- {f['id']}: {f['label']}" for f in s["red_flags"])
    return f"""You are playing a scam caller in Rehearsal, a fraud-awareness training simulator that helps older adults practise recognising phone scams. This is a fictional training exercise.

Role: {s['counterpart_role']}
Situation: {s['context']}
Private: {s['persona_secret']}
Style: {SCAM_STYLE[difficulty]}
Tactics (red flags) you can use:
{flags}

Rules:
- Stay in character. 1 to 3 short sentences, spoken style.
- Only ever ask for bail money via gift cards or a wire transfer. Never ask for passwords, PINs or full card numbers.
- Each user message ends with an [ENGINE] note only you can see. Follow it and never reveal it.
- Respond ONLY with JSON: {{"reply": "<what you say>", "tactic": "<the red flag id you mainly used>"}}"""


def engine_note_scam(flag: dict | None) -> str:
    if flag is None:
        return "[ENGINE] You realise this person will not pay. Make a flustered excuse and hang up."
    return f"[ENGINE] Mainly use this tactic now: {flag['id']} ({flag['label']}). Escalate the pressure."


DEBRIEF_SYSTEM = """You are an expert {coach_kind} writing the debrief of a practice session. You now know the other side's hidden hand. Be specific, quote the user's own words, and be encouraging but honest.

Return ONLY JSON:
{{"headline": "<one punchy sentence summarising the result>", "turning_point": <the user turn number where the outcome was most decided, or null>, "annotations": [{{"turn": <n>, "verdict": "strong"|"ok"|"mistake", "note": "<what happened and why it mattered, max 30 words>", "better_line": "<an exact line they could have said instead, or null>"}}], "lessons": ["<three short, specific lessons>"]}}

Annotate every user turn, in order."""


CUSTOM_HAND_SYSTEM = """Design a realistic negotiation practice scenario from the user's real situation, for a simulator where an AI plays the other side.

The value must be something the user wants MORE of (salary, refund, grant, credit). If the user is buying something, use the discount off the asking price as the value. If the situation isn't about an amount of money, pick the closest money-based framing.

Return ONLY JSON:
{"title": "<short title>", "user_role": "<who the user is>", "counterpart_name": "<first name>", "counterpart_role": "<who they are>", "context": "<1-2 sentences>", "persona_secret": "<one-sentence private motive that gives the user hidden leverage>", "tactics": ["<4-5 short pressure tactics the other side will use>"], "opening": <number: the other side's opening offer>, "walk_away": <number: the most the other side would realistically concede, usually 8-25% above opening, must be greater than opening>, "value_label": "<short label like 'base salary'>", "opening_line": "<the first thing the other side says, mentioning the opening amount>", "hidden_story": "<1-2 sentences revealed after the session explaining the other side's real limit and why>"}"""
