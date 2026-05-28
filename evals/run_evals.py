"""
Run the matcher against hand-crafted test cases and report accuracy.

Reads:
  - evals/cases.jsonl: {"description": "...", "acceptable": ["name1", ...]}
  - data/pokemon.json: built by scripts/fetch_pokemon.py

For each model passed via --models, this script re-encodes every Pokémon's
description blob in memory (we do not overwrite data/embeddings.npy), runs
every test case, and prints:
  - top-1 accuracy:   first match is in `acceptable`
  - top-5 accuracy:   any of the top-5 matches is in `acceptable`
  - mean rank:        avg index (1-based) of the best acceptable match,
                      or `n_pokemon` if none of the top-K were acceptable

Example:
  python evals/run_evals.py
  python evals/run_evals.py --models all-MiniLM-L6-v2 all-mpnet-base-v2
  python evals/run_evals.py --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

# Re-use the canonical blob-builder so evals stay in sync with build_index.py.
# Importing build_all_blobs (rather than the lower-level builder) means evals
# automatically pick up LLM-enriched personalities when data/personalities.json
# exists, so the metrics reflect what's actually in production
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_index import build_all_blobs, load_personalities  # noqa: E402

# Project paths
DATA_DIR = ROOT / "data"
POKEMON_FILE = DATA_DIR / "pokemon.json"
CASES_FILE = ROOT / "evals" / "cases.jsonl"

# Models to compare by default — small / medium / strong-small triplet
DEFAULT_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "BAAI/bge-small-en-v1.5",
]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_pokemon() -> list[dict[str, Any]]:
    if not POKEMON_FILE.exists():
        raise FileNotFoundError(
            f"{POKEMON_FILE} not found. Run scripts/fetch_pokemon.py first."
        )
    with POKEMON_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_cases() -> list[dict[str, Any]]:
    if not CASES_FILE.exists():
        raise FileNotFoundError(f"{CASES_FILE} not found.")
    cases: list[dict[str, Any]] = []
    with CASES_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


# ---------------------------------------------------------------------------
# Per-model evaluation
# ---------------------------------------------------------------------------

def evaluate_model(
    model_name: str,
    records: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    top_n: int = 5,
    verbose: bool = False,
) -> dict[str, Any]:
    print(f"\n=== Evaluating: {model_name} ===")
    model = SentenceTransformer(model_name)

    # Build the per-model index in memory (don't touch data/embeddings.npy)
    # build_all_blobs() automatically incorporates personalities.json if present
    names = [r["name"] for r in records]
    blobs = build_all_blobs(records)

    start = time.time()
    embeddings = model.encode(
        blobs,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)
    encode_time = time.time() - start

    # Run each case and collect rank of the first acceptable hit
    top1_hits = 0
    topk_hits = 0
    ranks: list[int] = []

    for case in cases:
        query = case["description"]
        acceptable = {name.lower() for name in case["acceptable"]}

        # Encode the query with the same model + normalization as the index
        query_vec = model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0].astype(np.float32)

        scores = embeddings @ query_vec
        # Sort top_n descending for ranked inspection
        top_indices = np.argpartition(-scores, kth=min(top_n, len(scores) - 1))[:top_n]
        top_indices = top_indices[np.argsort(-scores[top_indices])]
        ranked_names = [names[i] for i in top_indices]

        is_top1 = ranked_names[0] in acceptable
        is_topk = any(name in acceptable for name in ranked_names)

        top1_hits += int(is_top1)
        topk_hits += int(is_topk)

        # Rank of best acceptable hit (1-based); missing → len(records) as a stand-in
        rank = next(
            (i + 1 for i, name in enumerate(ranked_names) if name in acceptable),
            len(records),
        )
        ranks.append(rank)

        if verbose:
            marker = "PASS" if is_topk else "MISS"
            print(f"  [{marker}] '{query[:55]}'  ->  {ranked_names}")

    n = len(cases)
    return {
        "model": model_name,
        "n_cases": n,
        "top1_accuracy": top1_hits / n,
        "topk_accuracy": topk_hits / n,
        "mean_rank": float(np.mean(ranks)),
        "encode_time_s": encode_time,
        "embedding_dim": int(embeddings.shape[1]),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_summary(results: list[dict[str, Any]], top_n: int) -> None:
    print("\n" + "=" * 100)
    print("RESULTS")
    print("=" * 100)
    header = f"{'Model':<48} {'Dim':<5} {'Top-1':<8} {f'Top-{top_n}':<8} {'MeanRank':<10} {'Encode(s)':<10}"
    print(header)
    print("-" * 100)
    for r in results:
        print(
            f"{r['model']:<48} "
            f"{r['embedding_dim']:<5} "
            f"{r['top1_accuracy']:<8.3f} "
            f"{r['topk_accuracy']:<8.3f} "
            f"{r['mean_rank']:<10.2f} "
            f"{r['encode_time_s']:<10.1f}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Pokémon matcher accuracy.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="Models to evaluate (default: 3 baseline models).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Top-K to report (default: 5).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-case pass/miss with the top-K names.",
    )
    args = parser.parse_args()

    records = load_pokemon()
    cases = load_cases()
    print(f"Loaded {len(records)} Pokémon and {len(cases)} eval cases.")

    # Make it obvious which corpus flavor the eval is measuring
    personalities = load_personalities()
    if personalities:
        print(f"Corpus mode: ENRICHED (using {len(personalities)} LLM-generated personalities).")
    else:
        print("Corpus mode: BASELINE (no personalities.json found — run scripts/enrich_descriptions.py to enrich).")

    results = [
        evaluate_model(model, records, cases, top_n=args.top, verbose=args.verbose)
        for model in args.models
    ]
    print_summary(results, top_n=args.top)


if __name__ == "__main__":
    main()
