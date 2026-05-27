"""
FastAPI service exposing POST /match for the "What Pokémon Are You?" app.

Loads the embedding index + matcher + LLM explainer ONCE at startup so
per-request latency is just a query embedding + dot product + LLM call.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from explainer import Explainer
from matcher import PokemonMatcher

# Pick up .env automatically in local dev. Production envs (Railway) inject vars directly.
load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Comma-separated list of allowed CORS origins; defaults are local dev hosts.
_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class MatchRequest(BaseModel):
    # Free-text description is the only required field; the rest are optional
    # structured signals that get folded into the same query blob.
    description: str = Field(..., min_length=3, max_length=1000)
    color: str | None = Field(default=None, max_length=50)
    mood: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=100)


class PokemonResult(BaseModel):
    id: int
    name: str
    sprite_url: str | None
    types: list[str]
    stats: dict[str, int]
    score: float


class MatchResponse(BaseModel):
    pokemon: PokemonResult
    explanation: str
    runners_up: list[PokemonResult]
    llm_enabled: bool


# ---------------------------------------------------------------------------
# App + lifespan (one-time model/index loading)
# ---------------------------------------------------------------------------

# Globals populated by the lifespan handler — keeps endpoint code clean.
matcher: PokemonMatcher | None = None
explainer: Explainer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup: load embeddings + model + LLM client.
    global matcher, explainer

    logger.info("Loading matcher (embeddings + sentence-transformers model)...")
    matcher = PokemonMatcher()
    matcher.load()
    logger.info("Matcher ready.")

    explainer = Explainer()
    logger.info("Explainer ready (llm_enabled=%s).", explainer.llm_enabled)

    yield
    # No teardown needed; OS reclaims memory on shutdown.


app = FastAPI(
    title="What Pokémon Are You?",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS for the Next.js frontend (localhost in dev, Vercel URL in prod).
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_query_blob(req: MatchRequest) -> str:
    # Compose structured fields into the same natural-language style as the
    # description blobs so the embedding model treats them consistently.
    parts = [req.description.strip()]
    if req.color:
        parts.append(f"My favorite color is {req.color.strip()}.")
    if req.mood:
        parts.append(f"My mood is {req.mood.strip()}.")
    if req.environment:
        parts.append(f"I love being in {req.environment.strip()}.")
    return " ".join(parts)


def _to_result(record: dict[str, Any], score: float) -> PokemonResult:
    # Trim the raw record to just the fields the frontend needs.
    return PokemonResult(
        id=record["id"],
        name=record["name"],
        sprite_url=record.get("sprite_url"),
        types=record.get("types", []),
        stats=record.get("stats", {}),
        score=score,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root() -> dict[str, Any]:
    # Lightweight health-check that doubles as the home route on Railway.
    return {
        "service": "what-pokemon-are-you",
        "status": "ok",
        "matcher_ready": bool(matcher and matcher.ready),
        "llm_enabled": bool(explainer and explainer.llm_enabled),
    }


@app.post("/match", response_model=MatchResponse)
def match(req: MatchRequest) -> MatchResponse:
    if matcher is None or explainer is None:
        # Should be impossible once lifespan has run, but fail loudly if so.
        raise HTTPException(status_code=503, detail="Service still warming up.")

    query = _build_query_blob(req)
    matches = matcher.find_top_n(query, n=5)
    if not matches:
        raise HTTPException(status_code=500, detail="No matches found.")

    # Top match drives the explanation; the rest go in `runners_up` for UI flair.
    top = matches[0]
    explanation = explainer.explain(req.description, top.record)

    return MatchResponse(
        pokemon=_to_result(top.record, top.score),
        explanation=explanation,
        runners_up=[_to_result(m.record, m.score) for m in matches[1:]],
        llm_enabled=explainer.llm_enabled,
    )
