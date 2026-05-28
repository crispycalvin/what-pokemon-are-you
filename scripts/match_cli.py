"""
CLI for matching a free-text self-description to the nearest Pokémon.

Loads the pre-computed embedding index built by build_index.py, embeds the
user's input with the same model, and prints the top-N matches ranked by
cosine similarity.

Example:
  python scripts/match_cli.py "I'm a quiet reader who likes rainy days and tea"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

# Project paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
POKEMON_FILE = DATA_DIR / "pokemon.json"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.npy"
NAMES_FILE = DATA_DIR / "pokemon_names.json"

# Must match the model used in build_index.py for results to be meaningful
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Loading the index
# ---------------------------------------------------------------------------

def _load_index() -> tuple[np.ndarray, list[str], dict[str, dict[str, Any]]]:
    # Bail early with a clear message if the pipeline hasn't been run yet
    for required in (POKEMON_FILE, EMBEDDINGS_FILE, NAMES_FILE):
        if not required.exists():
            raise FileNotFoundError(
                f"Missing {required}. Run fetch_pokemon.py and build_index.py first."
            )

    # Pre-normalized vectors: cosine similarity == dot product
    embeddings = np.load(EMBEDDINGS_FILE)

    with NAMES_FILE.open("r", encoding="utf-8") as fh:
        names: list[str] = json.load(fh)

    # Look up full Pokémon records by name for nicer CLI output
    with POKEMON_FILE.open("r", encoding="utf-8") as fh:
        records: list[dict[str, Any]] = json.load(fh)
    by_name = {record["name"]: record for record in records}

    return embeddings, names, by_name


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def find_top_n(
    query: str,
    embeddings: np.ndarray,
    names: list[str],
    model: SentenceTransformer,
    n: int = 5,
) -> list[tuple[str, float]]:
    # Embed the query with the same normalization as the index
    query_vec = model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0].astype(np.float32)

    # Cosine similarity collapses to a single matmul thanks to normalization
    scores = embeddings @ query_vec

    # argpartition + sort is faster than a full sort for top-N on large arrays
    top_indices = np.argpartition(-scores, kth=min(n, len(scores) - 1))[:n]
    top_indices = top_indices[np.argsort(-scores[top_indices])]

    return [(names[i], float(scores[i])) for i in top_indices]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match a self-description to the nearest Pokémon."
    )
    parser.add_argument(
        "description",
        nargs="+",
        help="Free-text description of yourself (in quotes or as words).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="How many matches to show (default: 5)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Embedding model (must match build_index.py, default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    query = " ".join(args.description).strip()
    if not query:
        parser.error("Please provide a non-empty description.")

    embeddings, names, by_name = _load_index()

    print(f"Loading model: {args.model}")
    model = SentenceTransformer(args.model)

    matches = find_top_n(query, embeddings, names, model, n=args.top)

    # Pretty-print results with name, score, and a couple of context fields
    print(f'\nQuery: "{query}"\n')
    print(f"{'Rank':<5} {'Pokémon':<18} {'Score':<8} {'Types':<22} Flavor")
    print("-" * 100)
    for rank, (name, score) in enumerate(matches, start=1):
        record = by_name.get(name, {})
        types = "/".join(record.get("types", []))
        flavor = record.get("flavor_text", "")[:60]
        if len(record.get("flavor_text", "")) > 60:
            flavor += "..."
        print(f"{rank:<5} {name.title():<18} {score:<8.4f} {types:<22} {flavor}")


if __name__ == "__main__":
    main()
