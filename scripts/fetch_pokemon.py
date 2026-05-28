"""
Fetch every Pokémon from PokeAPI and cache a slim, embed-ready record per
Pokémon to data/pokemon.json.

Each record contains the fields we actually need downstream:
  - id, name, sprite_url, types, abilities, base stats, flavor text

We hit two endpoints per Pokémon (`/pokemon/{id}` and `/pokemon-species/{id}`)
because flavor text lives on the species endpoint. Individual responses are
cached to data/.cache/ so re-running the script is cheap and offline-friendly.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

# Project paths (script lives in scripts/, data lives in ../data/)
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / ".cache"
OUTPUT_FILE = DATA_DIR / "pokemon.json"

# PokeAPI endpoints
POKEAPI_BASE = "https://pokeapi.co/api/v2"
POKEMON_URL = POKEAPI_BASE + "/pokemon/{id}"
SPECIES_URL = POKEAPI_BASE + "/pokemon-species/{id}"

# Hard cap on how many Pokémon to fetch (PokeAPI exposes ~1025 as of 2026)
# Set high enough to grab everything; the loop short-circuits on 404
MAX_POKEMON_ID = 1025

# Be polite to the free public API to not overload the server
REQUEST_TIMEOUT_S = 30
RETRY_BACKOFF_S = 2.0


# ---------------------------------------------------------------------------
# HTTP + cache helpers
# ---------------------------------------------------------------------------

def _cache_path(key: str) -> Path:
    # Each cached JSON response gets its own file keyed by endpoint slug
    return CACHE_DIR / f"{key}.json"


def _get_json(url: str, cache_key: str) -> dict[str, Any] | None:
    # Return cached response if we've already fetched this URL
    cache_file = _cache_path(cache_key)
    if cache_file.exists():
        with cache_file.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    # Live fetch with a single retry on transient errors
    for attempt in range(2):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_S)
        except requests.RequestException:
            if attempt == 0:
                time.sleep(RETRY_BACKOFF_S)
                continue
            raise

        if response.status_code == 404:
            return None
        if response.status_code == 200:
            payload = response.json()
            # Persist to cache so future runs are instant + offline-capable
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with cache_file.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            return payload

        # Transient (5xx / rate limit) — back off once then retry
        if attempt == 0:
            time.sleep(RETRY_BACKOFF_S)
            continue
        response.raise_for_status()

    return None


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------

def _extract_english_flavor_text(species: dict[str, Any]) -> str:
    # Species returns a list of flavor texts across games/languages
    # Grab the first English entry and clean up control chars PokeAPI ships
    for entry in species.get("flavor_text_entries", []):
        language = entry.get("language", {}).get("name")
        if language == "en":
            text = entry.get("flavor_text", "")
            return text.replace("\n", " ").replace("\f", " ").replace("\r", " ").strip()
    return ""


def _stat_adjectives(stats: dict[str, int]) -> list[str]:
    # Convert base stats into rough adjectives so embeddings have something
    # human-readable to grab onto beyond raw numbers
    adjectives: list[str] = []

    if stats.get("speed", 0) >= 100:
        adjectives.append("fast")
    elif stats.get("speed", 0) <= 45:
        adjectives.append("slow")

    if stats.get("hp", 0) >= 100 or stats.get("defense", 0) >= 100:
        adjectives.append("bulky")
    elif stats.get("hp", 0) <= 40:
        adjectives.append("fragile")

    if stats.get("attack", 0) >= 110 or stats.get("special-attack", 0) >= 110:
        adjectives.append("hard-hitting")

    if stats.get("special-defense", 0) >= 100:
        adjectives.append("resilient")

    return adjectives


def _build_record(pokemon: dict[str, Any], species: dict[str, Any]) -> dict[str, Any]:
    # Flatten the two API payloads into the slim shape we need downstream
    stats = {s["stat"]["name"]: s["base_stat"] for s in pokemon.get("stats", [])}
    types = [t["type"]["name"] for t in pokemon.get("types", [])]
    abilities = [a["ability"]["name"].replace("-", " ") for a in pokemon.get("abilities", [])]

    sprites = pokemon.get("sprites", {})
    official_artwork = sprites.get("other", {}).get("official-artwork", {}).get("front_default")
    fallback_sprite = sprites.get("front_default")

    return {
        "id": pokemon["id"],
        "name": pokemon["name"],
        "types": types,
        "abilities": abilities,
        "stats": stats,
        "stat_adjectives": _stat_adjectives(stats),
        "flavor_text": _extract_english_flavor_text(species),
        "sprite_url": official_artwork or fallback_sprite,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []

    # Walk Pokédex IDs sequentially. PokeAPI is stable + paginated by ID
    for pokemon_id in tqdm(range(1, MAX_POKEMON_ID + 1), desc="Fetching Pokémon"):
        pokemon = _get_json(POKEMON_URL.format(id=pokemon_id), f"pokemon-{pokemon_id}")
        if pokemon is None:
            # Past the end of the live Pokédex — stop cleanly
            break

        species = _get_json(SPECIES_URL.format(id=pokemon_id), f"species-{pokemon_id}")
        if species is None:
            species = {}

        records.append(_build_record(pokemon, species))

    # Write the consolidated dataset that downstream scripts consume
    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)

    print(f"Wrote {len(records)} Pokémon to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
