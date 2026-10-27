import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, llm
from .engine import SCENARIOS, EngineError, Session, SessionStore, build_custom_scenario, public_scenario

log = logging.getLogger("rehearsal")
STATIC = Path(__file__).resolve().parent.parent / "static"
store = SessionStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    models = await llm.resolve_models()
    log.warning("Rehearsal models (mock=%s): %s", config.MOCK, models)
    yield


app = FastAPI(title="Rehearsal", lifespan=lifespan)

# The public demo spends real credits, so cap model-backed requests per visitor and overall.
_hits: dict[str, deque] = defaultdict(deque)
_all_hits: deque = deque()


def _over(q: deque, limit: int, window: float, now: float) -> bool:
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/api/"):
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
        now = time.monotonic()
        if _over(_hits[ip], config.RATE_PER_IP, 600, now) or _over(_all_hits, config.RATE_GLOBAL, 3600, now):
            return JSONResponse({"detail": "The demo is busy. Please wait a few minutes and try again."}, status_code=429)
    return await call_next(request)


class NewSession(BaseModel):
    scenario_id: str
    difficulty: str = "tough"
    situation: str | None = None


class Turn(BaseModel):
    session_id: str
    text: str = ""
    action: str | None = None


class SessionRef(BaseModel):
    session_id: str
    turn: int | None = None


def _bad(e: Exception):
    raise HTTPException(status_code=400 if isinstance(e, EngineError) else 502, detail=str(e))


@app.get("/api/health")
async def health():
    return {"ok": True, "mock": config.MOCK, "models": config.MODELS}


@app.get("/api/scenarios")
async def scenarios():
    return {"scenarios": [public_scenario(s) for s in SCENARIOS.values()], "models": config.MODELS, "mock": config.MOCK}


@app.post("/api/session")
async def new_session(body: NewSession):
    try:
        calls: list = []
        if body.scenario_id == "custom":
            scenario = await build_custom_scenario(body.situation or "", calls)
        elif body.scenario_id in SCENARIOS:
            scenario = SCENARIOS[body.scenario_id]
        else:
            raise EngineError("Unknown scenario.")
        session = Session(scenario, body.difficulty, calls)
    except (EngineError, llm.LLMError) as e:
        _bad(e)
    store.add(session)
    return session.snapshot_view()


@app.post("/api/turn")
async def turn(body: Turn):
    try:
        session = store.get(body.session_id)
    except EngineError as e:
        _bad(e)

    async def events():
        try:
            async for ev in session.turn(body.text, body.action):
                yield json.dumps(ev) + "\n"
        except (EngineError, llm.LLMError) as e:
            yield json.dumps({"type": "error", "message": str(e), "rolled_back": True}) + "\n"
        yield json.dumps({"type": "calls", "calls": session.calls}) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/debrief")
async def debrief(body: SessionRef):
    try:
        session = store.get(body.session_id)
        result = await session.make_debrief()
    except (EngineError, llm.LLMError) as e:
        _bad(e)
    return {"debrief": result, "calls": session.calls}


@app.post("/api/replay")
async def replay(body: SessionRef):
    try:
        return store.get(body.session_id).replay(body.turn or 1)
    except EngineError as e:
        _bad(e)


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")
