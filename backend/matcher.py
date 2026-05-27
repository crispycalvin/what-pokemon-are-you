"""
Cosine-similarity matcher backed by a pre-built NumPy embedding index.

Loads everything once (data/embeddings.npy + pokemon.json + the
sentence-transformers model) and exposes a single `find_top_n` method that
embeds a query and returns the top-K nearest Pokémon records with scores.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

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

    def find_top_n(self, query: str, n: int = 5) -> list[Match]:
        if not self.ready or self._model is None or self._embeddings is None:
            raise RuntimeError("Matcher not loaded. Call load() first.")

        # Encode the query with the same normalization as the index.
        query_vec = self._model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0].astype(np.float32)

        # Cosine similarity over the whole index in one matmul.
        scores = self._embeddings @ query_vec

        # Top-N partial sort is faster than a full argsort on 1k+ rows.
        n = min(n, len(scores))
        top_indices = np.argpartition(-scores, kth=n - 1)[:n]
        top_indices = top_indices[np.argsort(-scores[top_indices])]

        return [
            Match(rank=rank, score=float(scores[i]), record=self._records[i])
            for rank, i in enumerate(top_indices, start=1)
        ]
