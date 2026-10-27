"""List models on Nebius Token Factory and show which Nemotron IDs Rehearsal would auto-pick.

    python scripts/list_models.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, llm  # noqa: E402


async def main():
    if not config.API_KEY:
        sys.exit("NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key.")
    ids = sorted(m.id for m in (await llm.client().models.list()).data)
    nemotron = [i for i in ids if "nemotron" in i.lower()]
    print(f"{len(ids)} models available, {len(nemotron)} Nemotron:")
    for i in nemotron:
        print("  ", i)
    print("\nAuto-pick (override with NANO_MODEL / SUPER_MODEL / ULTRA_MODEL in .env):")
    for tier in config.TIERS:
        print(f"  {tier:5} -> {config.MODELS[tier] or llm.pick_model(ids, tier) or '(none found)'}")


asyncio.run(main())
