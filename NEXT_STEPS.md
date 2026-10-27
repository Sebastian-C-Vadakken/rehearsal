# Next steps

Last updated: Wed Oct 28, 2026. **The deadline is Thu Oct 29 at night, so tomorrow is submission day.** Aim to submit by about 8pm and keep the evening as buffer.

## Where we are

**Done**
- The app works end to end against the live Nemotron models on Nebius Token Factory. Models are auto-detected:
  - Nano: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (coach, reasoning off for speed)
  - Ultra: `nvidia/Nemotron-3-Ultra-550b-a55b` (opponent, debrief and custom scenarios, reasoning on)
- Scenarios: salary offer, deposit refund, financial-aid appeal, the "Grandma, it's me" scam, and "Rehearse your real situation". Each has Friendly, Tough and Hardball levels.
- Features: live coach meters, the Python deal engine that keeps the hidden walk-away, card-flip reveal, Ultra debrief with notes on each turn, "Replay from turn N", and the model router panel.
- `scripts/smoke_test.py --live` passes all 18 checks.
- Rate limit for the public demo: 60 requests per visitor per 10 minutes and 1,500 per hour overall.
- The Docker image is built and pushed publicly as **`docker.io/sebcv/rehearsal:v1`**.
- Commits are on the local `main` branch. **Nothing has been pushed to GitHub yet.**

**Not done**
- The GitHub repo (it must be public and show the MIT license)
- The Nebius Serverless Endpoint, which gives us the public demo URL
- The README TODOs: demo URL, video link, the Nebius services line, and the feedback section
- The real Nemotron prices in `.env.example` and on the endpoint. The current numbers are placeholders, so the router panel's cost estimate is wrong until they're replaced.
- The demo video and the submission form

## Tomorrow's plan

| Time | Step | Who |
|---|---|---|
| ~15 min | **1. Create the GitHub repo.** At https://github.com/new: name `rehearsal`, **Public**, with no README, .gitignore or license. Copy the URL. | You |
| ~5 min | **2. Push.** `git remote add origin <url>` then `git push -u origin main`. A GitHub login window may pop up. Check that the license shows at the top of the repo page. | Claude |
| ~45 min | **3. Deploy on Nebius.** In the console, go to Serverless → Endpoints → Create, using the values below. Wait for **Running**, then copy the `https://` address from **Public endpoints**. | You |
| ~30 min | **4. Test the public URL.** Play every scenario through the reveal, debrief and replay, on a laptop and a phone, in an incognito window. | Claude + you |
| ~45 min | **5. Playtest and tune.** Play a few rounds and note anything that feels off (whether Hardball is hard enough, whether the tips are specific). Tune the prompts, then rebuild and push `v2` if needed. | You + Claude |
| ~30 min | **6. README.** Fill in the demo URL, the Nebius services used, real prices, and the **feedback on Token Factory and Nemotron** (a required item). | Claude, using your notes |
| ~90 min | **7. Video (3 minutes or less, public on YouTube).** Use the script below. Record the public URL, not localhost. | You |
| ~30 min | **8. Submit.** Use the checklist below. | You |

### Nebius endpoint form

| Field | Value |
|---|---|
| Name | `rehearsal` |
| Image | `docker.io/sebcv/rehearsal:v1` |
| Container port | `8000` |
| Platform / preset | CPU only (e.g. `cpu-d3`), the smallest preset |
| Disk | `20 GiB` |
| Authentication | **None**, so judges can open it |
| Environment variable | `NEBIUS_API_KEY` = your key. **Type it in yourself; never paste it in chat.** |

The models are auto-detected, so no other variables are needed. The endpoint is billed while it's running; delete it after judging.

### Video script (≤ 3:00)
- **0:00 Cold open.** Salary scenario on Hardball. Ask for a range and accept, then the cards flip: "$X left on the table."
- **0:25 The problem.** New grads, tenants, first-gen students and seniors lose real money because they never practise and can't see the other side's hand.
- **0:50 Replay from the turning point.** Use the debrief's better line, watch the coach meters jump, and win more.
- **1:50 The scam scenario.** Hang up, and the red-flag checklist shows what you spotted and missed.
- **2:15 Under the hood.** Show the router panel (Nano for the coach, Ultra for the opponent), explain that the walk-away lives only in Python so Ultra never sees it, and mention the Nebius Serverless deploy.
- **2:45 Close.** "Lose the negotiation here, not in real life."

### Submission checklist (from HACKATHON.md)
- [ ] Track: **Best Apps and Agents**
- [ ] Project description: what it is, why, and how it works (adapt the README intro)
- [ ] Working demo URL (the Nebius endpoint)
- [ ] Public YouTube video, ≤ 3:00, showing Token Factory and Nemotron usage
- [ ] Public repo with the MIT license visible and a README with setup steps
- [ ] README covers how Nemotron and Token Factory were used, plus the Nebius services used
- [ ] Feedback on Token Factory and Nemotron
- [ ] Builders & Brews city, if you attended one

## Gotchas
- **Never read, print or paste `.env` or the API key.** Pass it with `--env-file .env` or type it into the Nebius console.
- The `!` prefix in Claude Code runs bash with no interactive input. Use forward slashes (`.venv/Scripts/python`), and run interactive logins (`docker login`, `git` auth) in a normal terminal or through Docker Desktop.
- Docker Desktop's access to PyPI is very slow on this machine. To rebuild the image, download the Linux wheels on the host and use the offline Dockerfile:
  ```bash
  .venv/Scripts/python -m pip download -d .wheels --only-binary=:all: --python-version 3.12 --implementation cp \
    --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux_2_28_x86_64 \
    -r requirements.txt "uvloop>=0.15.1"
  docker build -f scripts/Dockerfile.offline -t sebcv/rehearsal:v2 .
  docker push sebcv/rehearsal:v2
  ```
  Then change the image tag on the Nebius endpoint to `v2`.
- To run locally: `.venv/Scripts/uvicorn app.main:app --port 8000`, then open http://localhost:8000. Add `MOCK_LLM=1` to use no credits.
