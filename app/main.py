import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
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
