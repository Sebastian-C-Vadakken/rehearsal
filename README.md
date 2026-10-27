# Rehearsal

**Lose the negotiation here, not in real life.**

Rehearsal lets you practise high-stakes conversations against an AI opponent that holds a **hidden hand**. While you talk, a live coach scores every move you make. When the conversation ends, the cards flip: you see the other side's real limit, how much money you left on the table, and a turn-by-turn debrief. You can then **replay from the exact turn where you slipped**.

Built for the **Best Apps and Agents** track. Powered by **NVIDIA Nemotron** models on **Nebius Token Factory**.

> Demo: _TODO: hosted URL_ · Video: _TODO: YouTube link_

## Why

Most people don't lose money in negotiations because they argue badly. They lose it because they never practise, and because they can't see what the other side is holding back. The cost is real:

- **New grads and first-generation professionals** who accept the first salary offer
- **Tenants** who let a landlord keep a deposit for normal wear and tear
- **First-generation students** who never appeal a financial-aid award
- **Older adults** targeted by "grandparent" phone scams

Rehearsal gives each of them a safe opponent to lose to first.

## Scenarios

| Scenario | You want | Their hidden hand |
|---|---|---|
| New-grad salary offer | A higher base salary | Budget approved well above "the top of the band" |
| Security deposit refund | Your deposit back | Most deductions are for normal wear and tear |
| Financial-aid appeal | A bigger grant | A discretionary appeal fund |
| "Grandma, it's me" call | Not to get scammed | It's a scam; the payoff is gift cards |
| **Your own situation** | Paste your real offer | Nemotron Ultra builds a hidden hand from it |

Each scenario has three difficulty levels: Friendly, Tough and Hardball.

## How it works

```
 you type a move
      │
      ▼
 ┌────────────────┐   meters + tip (shown instantly)
 │ Nemotron Nano  │──────────────────────────────▶ live coach panel
 │  coach / judge │   anchoring, confidence, the amount you asked for...
 └───────┬────────┘
         │ structured read of your move
         ▼
 ┌────────────────┐   leverage = f(anchor, confidence, justification)
 │ Python deal    │   decides what the opponent is ALLOWED to offer this turn
 │ engine         │   holds the secret walk-away; validates every offer
 └───────┬────────┘
         │ "[ENGINE] your offer must be between $X and $Y"
         ▼
 ┌────────────────┐
 │ Nemotron Ultra │──▶ in-character reply + offer (JSON), streamed to the chat
 │  opponent      │
 └────────────────┘
 at the end: Python computes the reveal, then Ultra writes the debrief and per-turn notes
```

**Design choices that matter:**

- **The opponent model never sees the secret.** The walk-away number exists only in Python. Ultra is told only the range it may offer *this turn*. Asking "what's your max?" or attempting a prompt injection can't leak a number the model doesn't know, and every offer is validated before it reaches you.
- **Your move changes the outcome, not just the score.** Nano's read of your message (a specific number? a reason? hedging?) becomes a leverage multiplier that sets how far the opponent can move. Ask for a range and you get the bottom of it, just like in real life.
- **The math is deterministic.** Money left on the table and the percentage of available room you captured are computed in Python, not estimated by an LLM.
- **Branching replays.** Every turn is snapshotted, so you can rewind to the turning point and try the better line the debrief suggests.

## How we used NVIDIA Nemotron and Nebius Token Factory

| Call | Model | Why this tier |
|---|---|---|
| Coach: scores each user message (structured JSON) | **Nemotron Nano** | Runs on every turn, so it needs to be fast and cheap. Its output feeds the deal engine. |
| Opponent: in-character replies inside engine limits | **Nemotron Ultra** | Needs to stay in character, follow the hidden constraints, and use tactics well |
| Debrief: annotates every turn with a better line | **Nemotron Ultra** | Long-context reasoning over the transcript and the hidden hand |
| Custom scenario: builds a hidden hand from your real situation | **Nemotron Ultra** | Open-ended scenario design |

All calls go through Token Factory's OpenAI-compatible API. The **model router panel** in the app shows every call live: tier, latency, tokens, and the estimated cost compared with running everything on Ultra.

Nebius services used: **Token Factory** (inference) and **Serverless Endpoints** (hosting, _TODO: confirm_).

## Run it locally

Requires Python 3.11 or newer.

```bash
git clone <this repo> && cd rehearsal
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then set NEBIUS_API_KEY
python scripts/list_models.py   # shows the Nemotron models it will use
uvicorn app.main:app --reload
```

Open http://localhost:8000.

- **No API key?** Set `MOCK_LLM=1` to run the full UI on canned responses.
- **Tests:** `python scripts/smoke_test.py` runs every scenario end to end in mock mode. Add `--live` to run it against Token Factory.

### Docker / Nebius Serverless Endpoint

```bash
docker build -t rehearsal .
docker run -p 8000:8000 --env-file .env rehearsal
```

The same image can be deployed as a Nebius Serverless Endpoint (container port `8000`). Pass `NEBIUS_API_KEY` and, optionally, the model IDs as environment variables.

## Project layout

```
app/engine.py      deal engine: hidden hands, leverage, turn logic, replay, reveal, debrief
app/prompts.py     coach / opponent / debrief / custom-scenario prompts
app/llm.py         Token Factory client, model auto-detection, JSON parsing, call log
app/main.py        FastAPI routes (the turn endpoint streams NDJSON: coach → reply → reveal)
scenarios/*.json   preset hidden hands
static/            single-page UI (vanilla JS, no build step)
scripts/           smoke test, model listing
```

## Feedback on Nebius Token Factory and NVIDIA Nemotron

_TODO: write after building, covering what worked well and what was rough (setup, model catalog, latency, JSON reliability, docs)._

## License

MIT. See [LICENSE](LICENSE).
