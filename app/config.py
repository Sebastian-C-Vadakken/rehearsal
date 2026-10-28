import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NEBIUS_API_KEY", "").strip()
BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").strip()
MOCK = os.getenv("MOCK_LLM", "0").strip().lower() in ("1", "true", "yes") or not API_KEY

TIERS = ("nano", "super", "ultra")

# Filled in by llm.resolve_models() when left blank.
MODELS = {tier: os.getenv(f"{tier.upper()}_MODEL", "").strip() for tier in TIERS}


def _price(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


# USD per 1M tokens: (input, output). Defaults are Token Factory list prices for the Nemotron 3 models.
PRICES = {
    "nano": (_price("NANO_PRICE_IN", 0.06), _price("NANO_PRICE_OUT", 0.24)),
    "super": (_price("SUPER_PRICE_IN", 0.30), _price("SUPER_PRICE_OUT", 0.90)),
    "ultra": (_price("ULTRA_PRICE_IN", 1.00), _price("ULTRA_PRICE_OUT", 3.00)),
}

MAX_SESSIONS = 500

# ---- Budget guard for the public demo ----
# POST /api/* requests allowed per visitor per 10 minutes, and across everyone per hour.
RATE_PER_IP = int(os.getenv("RATE_PER_IP", "60"))
RATE_GLOBAL = int(os.getenv("RATE_GLOBAL", "600"))
# Estimated model spend allowed per UTC day; after that the demo shows "demo budget reached".
# Kept in memory, so it resets when a free host restarts the app; RATE_GLOBAL bounds spend per hour regardless.
DAILY_BUDGET_USD = _price("DAILY_BUDGET_USD", 3.00)
# User turns per round (accept / walk away / hang up always stay allowed), and model calls per session incl. replays.
MAX_TURNS = int(os.getenv("MAX_TURNS", "14"))
MAX_SESSION_CALLS = int(os.getenv("MAX_SESSION_CALLS", "80"))
# Output token ceilings per call type.
MAX_TOKENS = {"coach": 400, "counterpart": 1000, "debrief": 2500, "custom_scenario": 1500}
