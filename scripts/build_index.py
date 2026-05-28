"""
Turn data/pokemon.json into a searchable embedding index.

For each Pokémon we build a short "description blob" that captures vibe
(flavor text + types + abilities + stat adjectives), run it through a
sentence-transformers model, and save:
  - data/embeddings.npy       (N, D) float32 unit-normalized vectors
  - data/pokemon_names.json   parallel list of names so row i ↔ name[i]

Embeddings are L2-normalized so cosine similarity is just `query @ matrix.T`.
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
PERSONALITIES_FILE = DATA_DIR / "personalities.json"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.npy"
NAMES_FILE = DATA_DIR / "pokemon_names.json"

# Default embedding model — small + fast, good baseline
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Description-blob construction
# ---------------------------------------------------------------------------

def build_description_blob(record: dict[str, Any], personality: str | None = None) -> str:
    # Combine the most evocative fields into a single short paragraph the
    # embedding model can chew on. Keep it natural-language, not key/value.
    name = record.get("name", "").replace("-", " ")
    types = ", ".join(record.get("types", []))
    abilities = ", ".join(record.get("abilities", []))
    adjectives = ", ".join(record.get("stat_adjectives", []))
    flavor = record.get("flavor_text", "").strip()

    # Lead with the LLM-generated personality when available — it speaks the
    # same vocabulary users use about themselves, so it's the richest signal.
    # Otherwise fall back to leading with raw Pokédex flavor text.
    parts = []
    if personality:
        parts.append(personality)
    if flavor:
        parts.append(flavor)
    parts.append(f"{name.title()} is a {types}-type Pokémon.")
    if abilities:
        parts.append(f"Its abilities include {abilities}.")
    if adjectives:
        parts.append(f"It feels {adjectives}.")

    return " ".join(parts)


def load_personalities() -> dict[str, str]:
    # Returns {pokemon_name: personality_blurb} if the enrichment file exists,
    # else an empty dict (and downstream code falls back to baseline blobs).
    if not PERSONALITIES_FILE.exists():
        return {}
    with PERSONALITIES_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_all_blobs(records: list[dict[str, Any]]) -> list[str]:
    # Single entry point used by both build_index.py and run_evals.py so they
    # always stay in sync about whether personalities are mixed in.
    personalities = load_personalities()
    return [build_description_blob(r, personalities.get(r["name"])) for r in records]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build embedding index for Pokémon.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"sentence-transformers model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for encoding (default: 64)",
    )
    args = parser.parse_args()

    if not POKEMON_FILE.exists():
        raise FileNotFoundError(
            f"{POKEMON_FILE} not found. Run scripts/fetch_pokemon.py first."
        )

    # Load the cached dataset built by fetch_pokemon.py.
    with POKEMON_FILE.open("r", encoding="utf-8") as fh:
        records: list[dict[str, Any]] = json.load(fh)

    print(f"Loaded {len(records)} Pokémon records.")

    # Surface whether the index will be enriched or baseline, so the operator
    # knows what flavor of embeddings.npy they're about to produce.
    personalities = load_personalities()
    if personalities:
        print(f"Using LLM-generated personalities for {len(personalities)} Pokémon (enriched blobs).")
    else:
        print(f"No personalities.json found — building baseline blobs. Run scripts/enrich_descriptions.py for richer matching.")

    # Build one description blob per Pokémon, preserving row order.
    blobs = [build_description_blob(record, personalities.get(record["name"])) for record in records]
    names = [record["name"] for record in records]

    # Encode in batches with a progress bar; normalize for cosine similarity.
    print(f"Loading model: {args.model}")
    model = SentenceTransformer(args.model)

    print(f"Encoding {len(blobs)} blobs...")
    embeddings = model.encode(
        blobs,
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    # Persist embeddings + parallel name list so downstream code stays simple.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_FILE, embeddings)
    with NAMES_FILE.open("w", encoding="utf-8") as fh:
        json.dump(names, fh, indent=2)

    print(f"Saved embeddings to {EMBEDDINGS_FILE} (shape={embeddings.shape}, dtype={embeddings.dtype})")
    print(f"Saved name index to {NAMES_FILE}")


if __name__ == "__main__":
    main()
