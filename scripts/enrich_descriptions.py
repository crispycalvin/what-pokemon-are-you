"""
Generate a 2-3 sentence personality / vibe description for every Pokémon,
using Groq's free-tier Llama-3.1 model.

Why this exists: PokeAPI flavor text describes what Pokémon *do* (mechanics,
lore), not their *personality*. When a user types "quiet bookworm who likes
rainy days", embedding similarity has nothing personality-shaped to match
against. This script pre-generates personality blobs that *do* speak the same
language users use about themselves, then `build_index.py` folds them into the
description blobs before embedding.

Output: data/personalities.json — a flat dict { pokemon_name: "..." }.

The script is **resumable**: if personalities.json already exists, names that
are already present are skipped. Progress is saved incrementally so a crash
or rate-limit loses at most SAVE_EVERY entries.

Usage:
  python scripts/enrich_descriptions.py
  python scripts/enrich_descriptions.py --delay 1.0 --limit 100
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq, RateLimitError
from tqdm import tqdm

# Project paths.
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
POKEMON_FILE = DATA_DIR / "pokemon.json"
OUTPUT_FILE = DATA_DIR / "personalities.json"

# Groq config — same fast/free model used by the runtime explainer.
DEFAULT_MODEL = "llama-3.1-8b-instant"

# Default pacing: 2s between calls keeps us comfortably under the free-tier
# 30 RPM limit. Lower with --delay if you have a paid account.
DEFAULT_DELAY_S = 2.0

# Persist progress every N successful generations.
SAVE_EVERY = 25

# Per-call retry budget for rate limits / transient errors.
MAX_RETRIES = 4


SYSTEM_PROMPT = (
    "You are a Pokémon personality expert. Given a Pokémon's name, types, "
    "abilities, and Pokédex entry, write a 2-3 sentence personality / vibe "
    "description focused on:\n"
    "- Temperament (calm, fiery, mischievous, gentle, etc.)\n"
    "- Energy level and pace (lazy, hyperactive, focused, etc.)\n"
    "- Social tendencies (loner, social, protective, mysterious, etc.)\n"
    "- What kind of human personality or mood this Pokémon parallels\n\n"
    "Use vivid, evocative language. Focus on personality and vibe — what kind "
    "of person would resonate with this Pokémon. Do NOT describe its battle "
    "abilities, stats, evolution, or game mechanics. Do not invent facts "
    "beyond the Pokédex entry. Keep it to 2-3 sentences max."
)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _user_prompt(record: dict[str, Any]) -> str:
    # Pack the canonical fields the LLM needs into a single user message.
    name = record["name"].replace("-", " ").title()
    types = ", ".join(record.get("types", []))
    abilities = ", ".join(record.get("abilities", []))
    flavor = record.get("flavor_text", "").strip() or "(no Pokédex entry available)"

    return (
        f"Name: {name}\n"
        f"Types: {types}\n"
        f"Abilities: {abilities}\n"
        f"Pokédex entry: {flavor}\n\n"
        "Personality:"
    )


# ---------------------------------------------------------------------------
# Groq call with retry / backoff
# ---------------------------------------------------------------------------

def generate_personality(
    client: Groq,
    record: dict[str, Any],
    model: str,
) -> str | None:
    # Returns the LLM-generated personality string, or None if every retry fails.
    prompt = _user_prompt(record)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=200,
            )
            content = response.choices[0].message.content
            return (content or "").strip() or None

        except RateLimitError:
            # Exponential backoff on rate-limit errors specifically.
            wait = 2 ** (attempt + 1)
            tqdm.write(f"  rate-limited, sleeping {wait}s before retry...")
            time.sleep(wait)

        except Exception as exc:
            # Transient network / API blip — short sleep + retry.
            tqdm.write(f"  error ({exc}), retrying in 3s...")
            time.sleep(3)

    return None


# ---------------------------------------------------------------------------
# Atomic save helper
# ---------------------------------------------------------------------------

def save_atomic(data: dict[str, str], path: Path) -> None:
    # Write to a temp file then rename so a crash mid-write can't corrupt the cache.
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate LLM personality descriptions for every Pokémon."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_S,
        help=f"Seconds between calls (default: {DEFAULT_DELAY_S}, polite for free tier).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only enrich the first N un-cached Pokémon (useful for testing).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Groq model name (default: {DEFAULT_MODEL}).",
    )
    args = parser.parse_args()

    # Load GROQ_API_KEY from backend/.env (the canonical place we keep it).
    load_dotenv(ROOT / "backend" / ".env")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        sys.exit(
            "GROQ_API_KEY not set. Add it to backend/.env or export it in your shell.\n"
            "Get a free key at https://console.groq.com."
        )
    client = Groq(api_key=api_key)

    # Load source records.
    if not POKEMON_FILE.exists():
        sys.exit(f"{POKEMON_FILE} not found. Run scripts/fetch_pokemon.py first.")
    with POKEMON_FILE.open("r", encoding="utf-8") as fh:
        records: list[dict[str, Any]] = json.load(fh)

    # Resume from any existing cache so re-runs only fill the gaps.
    personalities: dict[str, str] = {}
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("r", encoding="utf-8") as fh:
            personalities = json.load(fh)
        print(f"Loaded {len(personalities)} cached personalities — skipping those.")

    # Work queue = records that are not yet in the cache.
    pending = [r for r in records if r["name"] not in personalities]
    if args.limit is not None:
        pending = pending[: args.limit]

    if not pending:
        print(f"Nothing to do. All {len(records)} Pokémon already enriched.")
        return

    estimated_min = (len(pending) * args.delay) / 60
    print(
        f"Generating {len(pending)} new personalities (of {len(records)} total) "
        f"at ~{args.delay}s/call. Estimated wall time: {estimated_min:.1f} min."
    )

    # Main enrichment loop.
    successes = 0
    for i, record in enumerate(tqdm(pending, desc="Enriching"), start=1):
        personality = generate_personality(client, record, model=args.model)
        if personality:
            personalities[record["name"]] = personality
            successes += 1
        else:
            tqdm.write(f"  ✗ skipped {record['name']} after retries")

        # Periodic checkpoint so a crash loses at most SAVE_EVERY entries.
        if i % SAVE_EVERY == 0:
            save_atomic(personalities, OUTPUT_FILE)

        # Polite delay between calls.
        time.sleep(args.delay)

    save_atomic(personalities, OUTPUT_FILE)
    print(
        f"\nDone. {successes}/{len(pending)} new personalities generated.\n"
        f"Total cached: {len(personalities)} → {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
