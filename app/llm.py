"""Token Factory client: model routing, JSON parsing, per-call logging."""

import json
import re
import time
from datetime import datetime, timezone

from openai import AsyncOpenAI

from . import config, mock

_client: AsyncOpenAI | None = None

# Skip non-chat Nemotron variants when auto-detecting.
_EXCLUDE = ("vl", "embed", "rerank", "reward", "guard", "safety", "parse", "retriever")


class LLMError(RuntimeError):
    pass


BUDGET_MESSAGE = ("Today's demo budget has been reached, so Rehearsal is resting until 00:00 UTC. "
                  "Thanks for trying it! The demo video shows a full round.")


class BudgetExceeded(LLMError):
    pass


# Estimated spend for the current UTC day (in memory; resets if the app restarts).
_spend = {"day": "", "usd": 0.0}


def spent_today() -> float:
    today = datetime.now(timezone.utc).date().isoformat()
    if _spend["day"] != today:
        _spend.update(day=today, usd=0.0)
    return _spend["usd"]


def budget_left() -> bool:
    return spent_today() < config.DAILY_BUDGET_USD


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=config.BASE_URL, api_key=config.API_KEY, timeout=90, max_retries=2)
    return _client


def pick_model(ids: list[str], tier: str) -> str:
    candidates = [
        i for i in ids
        if "nemotron" in i.lower() and tier in i.lower() and not any(x in i.lower() for x in _EXCLUDE)
    ]
    # Prefer the newest-looking ID (Nemotron 3 over older releases).
    candidates.sort(key=lambda i: ("nemotron-3" in i.lower() or "nemotron3" in i.lower(), i))
    return candidates[-1] if candidates else ""


async def resolve_models() -> dict:
    if config.MOCK:
        for tier in config.TIERS:
            config.MODELS[tier] = config.MODELS[tier] or f"mock/nemotron-{tier}"
        return config.MODELS
    if all(config.MODELS.values()):
        return config.MODELS
    ids = [m.id for m in (await client().models.list()).data]
    for tier in config.TIERS:
        if not config.MODELS[tier]:
            config.MODELS[tier] = pick_model(ids, tier)
    m = config.MODELS
    m["ultra"] = m["ultra"] or m["super"]
    m["super"] = m["super"] or m["ultra"] or m["nano"]
    m["nano"] = m["nano"] or m["super"]
    if not m["nano"] or not m["ultra"]:
        nemotron = [i for i in ids if "nemotron" in i.lower()]
        raise LLMError(f"Could not auto-detect Nemotron models. Set NANO_MODEL / ULTRA_MODEL in .env. Nemotron IDs available: {nemotron}")
    return m


def parse_json(text: str) -> dict:
    # Reasoning models may emit a <think> block before the answer.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def cost(tier: str, prompt_tokens: int, completion_tokens: int) -> float:
    p_in, p_out = config.PRICES[tier]
    return (prompt_tokens * p_in + completion_tokens * p_out) / 1_000_000


async def chat_json(tier: str, purpose: str, messages: list[dict], log: list, *,
                    max_tokens: int = 1200, temperature: float = 0.6, validate=None,
                    thinking: bool = True) -> dict:
    """Call a model tier, parse a JSON object reply, retry once with the error if invalid.

    thinking=False turns off Nemotron 3 reasoning: ~2x faster for simple scoring calls.
    """
    model = config.MODELS[tier]
    msgs = list(messages)
    max_tokens = min(max_tokens, config.MAX_TOKENS.get(purpose, max_tokens))
    extra = {} if thinking else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    last_err = ""
    for _ in range(2):
        if not budget_left():
            raise BudgetExceeded(BUDGET_MESSAGE)
        t0 = time.perf_counter()
        if config.MOCK:
            text = await mock.respond(purpose, msgs)
            pt, ct = sum(len(m["content"]) for m in msgs) // 4, len(text) // 4
        else:
            try:
                resp = await client().chat.completions.create(
                    model=model, messages=msgs, max_tokens=max_tokens, temperature=temperature, **extra)
            except Exception as e:  # network / API errors surface to the UI
                raise LLMError(f"{tier} call failed: {e}") from e
            text = resp.choices[0].message.content or ""
            if not text.strip() and resp.choices[0].finish_reason == "length":
                text = "(ran out of tokens while reasoning)"
            pt = resp.usage.prompt_tokens if resp.usage else 0
            ct = resp.usage.completion_tokens if resp.usage else 0
        log.append({
            "tier": tier, "model": model, "purpose": purpose,
            "ms": round((time.perf_counter() - t0) * 1000), "prompt_tokens": pt, "completion_tokens": ct,
            "cost": cost(tier, pt, ct), "ultra_cost": cost("ultra", pt, ct),
        })
        spent_today()  # roll the day over before adding
        _spend["usd"] += log[-1]["cost"]
        try:
            data = parse_json(text)
            if validate:
                validate(data)
            return data
        except ValueError as e:
            last_err = str(e)
            msgs = msgs + [
                {"role": "assistant", "content": text[-2000:]},
                {"role": "user", "content": f"That reply was invalid ({e}). Respond with ONLY the corrected JSON object."},
            ]
    raise LLMError(f"{tier} returned invalid output for {purpose}: {last_err}")

