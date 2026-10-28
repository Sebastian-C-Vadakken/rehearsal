---
title: Rehearsal
emoji: 🃏
colorFrom: yellow
colorTo: green
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Spar with a Nemotron opponent that holds a hidden hand
---

# Rehearsal

**Lose the negotiation here, not in real life.**

Practise a salary offer, a deposit refund, a financial-aid appeal, or a phone-scam call against an AI opponent with a **hidden hand**. A live coach scores every message you send. At the end the cards flip and show exactly what you left on the table, and you can replay from the turn where you slipped.

**Judges:** click **"Judge demo: salary offer"** on the home page for a guided round that takes about 2 minutes.

## How it's powered

Every model call goes **directly to NVIDIA Nemotron models on Nebius Token Factory**, through its OpenAI-compatible API, using the project's own key. This Space only hosts the web app and doesn't use Hugging Face inference.

- **Nemotron 3 Nano** scores each move (the coach)
- **Nemotron 3 Ultra** plays the opponent and writes the debrief

The opponent's real limit lives only in Python, so the model never sees it.

Code, setup and architecture: https://github.com/Sebastian-C-Vadakken/rehearsal (MIT)
