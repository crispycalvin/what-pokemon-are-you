"""
Hybrid matcher: cosine-similarity embedding search + type-affinity boosting.

Loads everything once (data/embeddings.npy + pokemon.json + the
sentence-transformers model) and exposes a single `find_top_n` method.

Scoring is two-stage:
  1. Retrieve the top CANDIDATE_POOL candidates by raw cosine similarity.
  2. Add type-affinity bonuses for each candidate based on the user's
     structured fields (environment, color, mood), then re-rank.

This ensures the structured fields meaningfully influence the result
(e.g. "environment: ocean" surfaces water-types) without completely
overriding a strong semantic match.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from type_affinity import compute_type_bonus

# Default data dir resolves to <repo>/data when running locally.
# Docker overrides via DATA_DIR env var.
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Must match scripts/build_index.py for similarity scores to be meaningful.
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


@dataclass
class Match:
    # A single ranked result. `record` is the full Pokémon dict from pokemon.json.
    rank: int
    score: float
    record: dict[str, Any]


class PokemonMatcher:
    """Owns the embedding matrix + Pokémon records and serves top-K queries."""

    def __init__(
        self,
        data_dir: Path | str | None = None,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR") or _DEFAULT_DATA_DIR)
        self.model_name = model_name

        # Lazy-loaded so __init__ stays cheap; call `load()` from FastAPI lifespan.
        self._model: SentenceTransformer | None = None
        self._embeddings: np.ndarray | None = None
        self._records: list[dict[str, Any]] = []
        self._name_to_record: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        # Reads index + records from disk and warms up the embedding model.
        embeddings_path = self.data_dir / "embeddings.npy"
        pokemon_path = self.data_dir / "pokemon.json"
        names_path = self.data_dir / "pokemon_names.json"

        for required in (embeddings_path, pokemon_path, names_path):
            if not required.exists():
                raise FileNotFoundError(
                    f"Missing {required}. Run fetch_pokemon.py + build_index.py."
                )

        # Pre-normalized vectors: cosine similarity collapses to a dot product.
        self._embeddings = np.load(embeddings_path)

        with pokemon_path.open("r", encoding="utf-8") as fh:
            self._records = json.load(fh)
        with names_path.open("r", encoding="utf-8") as fh:
            names: list[str] = json.load(fh)

        # Reorder records to match the embedding row order (row i ↔ names[i]).
        by_name = {record["name"]: record for record in self._records}
        self._records = [by_name[name] for name in names]
        self._name_to_record = by_name

        # Load the sentence-transformers model into memory.
        self._model = SentenceTransformer(self.model_name)

    @property
    def ready(self) -> bool:
        # True once load() has finished successfully.
        return self._model is not None and self._embeddings is not None

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    # How many candidates to pull from cosine-sim before re-ranking with
    # type bonuses. Large enough to give the boost room to surface the right
    # Pokémon; small enough to stay fast (still just a list comprehension).
    _CANDIDATE_POOL = 50

    def find_top_n(
        self,
        query: str,
        n: int = 5,
        *,
        environment: str | None = None,
        color: str | None = None,
        mood: str | None = None,
    ) -> list[Match]:
        if not self.ready or self._model is None or self._embeddings is None:
            raise RuntimeError("Matcher not loaded. Call load() first.")

        # --- Stage 1: semantic retrieval ---
        # Encode the query with the same normalization as the index.
        query_vec = self._model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0].astype(np.float32)

        # Cosine similarity over the whole index in one matmul (~1ms).
        cosine_scores = self._embeddings @ query_vec

        # Pull a wider candidate pool so the re-ranking step has room to
        # surface a better-typed Pokémon that narrowly missed the top-N.
        pool_size = min(self._CANDIDATE_POOL, len(cosine_scores))
        pool_indices = np.argpartition(-cosine_scores, kth=pool_size - 1)[:pool_size]

        # --- Stage 2: hybrid re-ranking with type-affinity bonuses ---
        # For each candidate, add structured-field type bonuses to the cosine score.
        hybrid_scores: list[tuple[float, int]] = []
        for i in pool_indices:
            record = self._records[i]
            bonus = compute_type_bonus(
                record.get("types", []),
                environment=environment,
                color=color,
                mood=mood,
            )
            hybrid_scores.append((float(cosine_scores[i]) + bonus, int(i)))

        # Sort candidates by combined score descending, take top-N.
        hybrid_scores.sort(key=lambda x: x[0], reverse=True)
        top_n = hybrid_scores[:n]

        return [
            Match(rank=rank, score=combined_score, record=self._records[idx])
            for rank, (combined_score, idx) in enumerate(top_n, start=1)
        ]
