# Next steps

Last updated: Wed Oct 28, 2026, evening. **The deadline is Thu Oct 29 at night.** The demo must stay live until **Dec 15**.

## Where we are

**Done**
- The app works end to end against the live Nemotron models on Nebius Token Factory:
  - Nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` runs the coach
  - Ultra `nvidia/Nemotron-3-Ultra-550b-a55b` runs the opponent, debrief and custom scenarios
- Code is public at https://github.com/Sebastian-C-Vadakken/rehearsal (MIT license detected).
- Budget guard: a $3/day spend ceiling with a friendly banner, a rate limit per visitor and overall, a turn cap per round, a call cap per session, and output-token limits. Raw model errors are hidden from visitors.
- The "Judge demo: salary offer" button runs a guided round of about 2 minutes.
- The mock smoke test has 22 checks, all passing. Earlier live runs passed all 18 checks before the budget checks were added.
- Hugging Face Space packaging: `space/README.md` (sdk: docker, app_port: 8000) and `scripts/deploy_space.py` (uploads an allowlist only and refuses `.env` files).

**Change of plan:** the Nebius Serverless deploy is skipped. The demo is hosted on a **Hugging Face Docker Space**, and the app still calls Nemotron **directly through Token Factory**. Don't use Hugging Face Inference Providers; the hackathon rules ban that. The old `docker.io/sebcv/rehearsal:v1` image is no longer needed.

**Not done**
- Rotate the Nebius API key. Part of the old one was exposed on Oct 28. Use the new key as the Space secret.
- Create the Space, add the secret, deploy, and test the public URL
- The README TODOs: demo URL, video link, and the feedback section
- The video, then the submission

## Plan

| Step | What | Who |
|---|---|---|
| 1 | Rotate the Nebius key in Token Factory and update `.env` locally | You |
| 2 | Create a Hugging Face account and a Docker Space named `rehearsal` (CPU basic, Public, Blank template) | You |
| 3 | In the Space: Settings → Variables and secrets → **New secret** `NEBIUS_API_KEY` | You |
| 4 | Create a Hugging Face **write** token, then run `hf auth login` in your own PowerShell window | You |
| 5 | Run `scripts/deploy_space.py <user>/rehearsal --dry-run`, then the real upload | Claude |
| 6 | Wait for **Running**, then test the public URL using the checklist below | Claude + you |
| 7 | Fill in the README demo URL and the feedback section | Claude |
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
- [ ] Working demo URL (the Hugging Face Space)
- [ ] Public YouTube video, ≤ 3:00, showing Token Factory and Nemotron usage
- [ ] Public repo with the MIT license visible, plus a README with setup steps, Nemotron and Token Factory usage, and the Nebius services used
- [ ] Feedback on Token Factory and Nemotron
- [ ] Builders & Brews city, if you attended one

## Gotchas
- **Never read, print, paste or commit `.env` or the API key.** On Hugging Face, the key is a Space **secret**, not a variable.
- Free CPU Spaces **sleep after about 48 hours with no visitors** and take roughly a minute to wake. Open the Space before judging windows, and do a final check around Dec 15.
- The budget counter is kept in memory, so it resets if the Space restarts. To change the ceiling, add a Space **variable** `DAILY_BUDGET_USD` (e.g. `2`).
- The `!` prefix in Claude Code can't take interactive input. Run logins (`hf auth login`, `docker login`) in your own terminal.
- To run locally: `.venv/Scripts/uvicorn app.main:app --port 8000`. Add `MOCK_LLM=1` to use no credits.
