# Next steps

Last updated: Thu Oct 29, 2026. **The deadline is Thu Oct 29 at night.** The demo must stay live until **Dec 15**.

## Where we are

**Done**
- The app works end to end against the live Nemotron models on Nebius Token Factory:
  - Nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` runs the coach
  - Ultra `nvidia/Nemotron-3-Ultra-550b-a55b` runs the opponent, debrief and custom scenarios
- Code is public at https://github.com/Sebastian-C-Vadakken/rehearsal (MIT license detected).
- Budget guard: a $3/day spend ceiling with a friendly banner, a rate limit per visitor and overall, a turn cap per round, a call cap per session, and output-token limits. Raw model errors are hidden from visitors.
- The "Judge demo: salary offer" button runs a guided round of about 2 minutes.
- The mock smoke test has 22 checks, all passing. Earlier live runs passed all 18 checks before the budget checks were added.
- Ready for Render: the app listens on `$PORT`, `/health` responds for health checks, and a "Free hosting: first load may take about 1 minute to wake up" note is at the top of the README and the app.

**Hosting:** a **Render free web service**, built from this repo's `Dockerfile`. The Nebius Serverless and Hugging Face plans are dropped. The app still calls Nemotron **directly through Token Factory** with our own key, and no other inference route is used. The old `docker.io/sebcv/rehearsal:v1` image is no longer needed.

**Not done**
- ✅ Nebius API key rotated and the old key revoked (the new key is in `.env` and on Render)
- ✅ Deployed on Render: https://rehearsal-syz0.onrender.com (tested end to end on Oct 28)
- ✅ README demo URL and feedback section
- The README video link (the last TODO)
- The video, then the submission

## Plan

| Step | What | Who |
|---|---|---|
| 1 | ✅ Rotate the Nebius key (done) | You |
| 2 | On render.com: **New → Web Service**, then connect the GitHub repo `rehearsal` | You |
| 3 | Settings: Docker, **Free** plan, env var `NEBIUS_API_KEY`, Health Check Path `/health`, then **Deploy** | You |
| 4 | Wait for **Live**, then copy the `https://….onrender.com` URL | You |
| 5 | Test the public URL using the checklist | Claude + you |
| 6 | Pushing to `main` redeploys automatically | (automatic) |
| 7 | ✅ Fill in the README demo URL and the feedback section (done) | Claude |
| 7b | Paste the YouTube link into the README `Video:` TODO | Claude, once you have the link |
| 8 | Record the video (≤ 3:00, public on YouTube) | You |
| 9 | Submit (see the checklist below) | You |

### Video script (≤ 3:00)
- **0:00 Cold open.** "Judge demo: salary offer". Send the suggested range ask, accept, and the cards flip: "$X left on the table."
- **0:25 The problem.** New grads, tenants, first-gen students and seniors lose real money because they never practise and can't see the other side's hand.
- **0:50 Replay from the turning point.** Use the debrief's better line, watch the coach meters jump, and win more.
- **1:50 The scam scenario.** Hang up, and the red-flag checklist shows what you spotted and missed.
- **2:15 Under the hood.** Show the router panel (Nano for the coach, Ultra for the opponent, all on Token Factory) and explain that the walk-away lives only in Python, so Ultra never sees it.
- **2:45 Close.** "Lose the negotiation here, not in real life."

### Submission checklist
- [ ] Track: **Best Apps and Agents**
- [ ] Project description: what it is, why, and how it works
- [ ] Working demo URL (the Render `onrender.com` URL)
- [ ] Public YouTube video, ≤ 3:00, showing Token Factory and Nemotron usage
- [ ] Public repo with the MIT license visible, plus a README with setup steps, Nemotron and Token Factory usage, and the Nebius services used
- [ ] Feedback on Token Factory and Nemotron
- [ ] Builders & Brews city, if you attended one

## Project description (ready to paste)

**Rehearsal: lose the negotiation here, not in real life.**

**What it is.** Rehearsal lets you practise high-stakes conversations, such as a salary offer, a deposit dispute, a financial-aid appeal or a scam phone call, against an AI opponent that holds a hidden hand. A live coach scores every move as you make it. When the round ends, the cards flip: you see the other side's real limit, how much money you left on the table, and a turn-by-turn debrief. Then you can replay from the exact turn where you slipped. You can also paste your own real situation, and Nemotron Ultra builds a hidden hand for it.

**Why.** Most people don't lose money in negotiations because they argue badly. They lose it because they never practise and can't see what the other side is holding back. New grads accept the first offer, tenants let landlords keep deposits for normal wear and tear, first-generation students never appeal an aid award, and older adults fall for "grandparent" scams. Rehearsal gives each of them a safe opponent to lose to first.

**How it works.** Every turn uses three NVIDIA Nemotron 3 models on Nebius Token Factory, each picked for its job. Nemotron Nano, with Super as a hedged backup after 3 s, reads your message as structured JSON: did you anchor, justify, or hedge? A deterministic Python deal engine turns that read into leverage and decides what the opponent may offer this turn. Nemotron Ultra then plays the opponent in character, within that range. The walk-away number exists only in Python, so Ultra never sees it, and no prompt injection can leak it. At the end, Python computes the reveal and Ultra writes the debrief. A live router panel shows every call's model, latency, tokens and cost. The public demo has a budget guard: a daily spend ceiling, rate limits and turn caps.

**Built with:** NVIDIA Nemotron 3 Nano, Super and Ultra · Nebius Token Factory (OpenAI-compatible API) · FastAPI · vanilla JS · hosted on Render.

**Links:** demo https://rehearsal-syz0.onrender.com (click "Judge demo: salary offer") · code https://github.com/Sebastian-C-Vadakken/rehearsal

## Gotchas
- **Never read, print, paste or commit `.env` or the API key.** On Render it's an environment variable that only you set.
- Render's free tier **sleeps after about 15 minutes without traffic**, and the first load then takes about a minute (hence the note). It allows 750 free instance-hours a month, which is enough to stay live until Dec 15.
- The daily budget counter is kept in memory, so it resets whenever Render restarts the app, including after sleep. `RATE_GLOBAL` (600 requests/hour) bounds spend no matter what. To change limits, add `DAILY_BUDGET_USD` or `RATE_GLOBAL` as Render environment variables.
- The `!` prefix in Claude Code can't take interactive input. Run logins in your own terminal.
- To run locally: `.venv/Scripts/uvicorn app.main:app --port 8000`. Add `MOCK_LLM=1` to use no credits.
