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


# USD per 1M tokens: (input, output)
PRICES = {
    "nano": (_price("NANO_PRICE_IN", 0.06), _price("NANO_PRICE_OUT", 0.24)),
    "super": (_price("SUPER_PRICE_IN", 0.10), _price("SUPER_PRICE_OUT", 0.40)),
    "ultra": (_price("ULTRA_PRICE_IN", 0.60), _price("ULTRA_PRICE_OUT", 1.80)),
}

MAX_SESSIONS = 500
