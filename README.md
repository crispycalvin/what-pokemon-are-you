# what-pokemon-are-you

Semantic "what Pokémon are you?" matcher. Describe yourself in plain English
and get the Pokémon whose Pokédex vibe is closest to yours, scored by
embedding similarity.

> **Status:** Phase 1 complete — Python data pipeline + CLI matcher.
> Frontend, API, and LLM-generated explanations land in later phases.

## How it works (Phase 1)

```
PokeAPI ──► scripts/fetch_pokemon.py ──► data/pokemon.json
                                            │
                                            ▼
                              scripts/build_index.py
                                            │
                                            ▼
                              data/embeddings.npy + pokemon_names.json
                                            │
                                            ▼
        User text ──► scripts/match_cli.py ──► top-N Pokémon (cosine sim)
```

Each Pokémon is reduced to a short "description blob" — flavor text + types +
abilities + stat-derived adjectives like *fast*, *bulky*, *fragile*. Every
blob is embedded with `all-MiniLM-L6-v2`, normalized, and stored as a single
NumPy matrix. Matching is just a dot product against that matrix.

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run the pipeline

```bash
# 1. Pull + cache every Pokémon from PokeAPI (~5–10 min first time, instant after).
python scripts/fetch_pokemon.py

# 2. Build the embedding index (~1–2 min on CPU).
python scripts/build_index.py

# 3. Match yourself.
python scripts/match_cli.py "I'm a quiet reader who likes rainy days and tea"
```

Sample output:

```
Query: "I'm a quiet reader who likes rainy days and tea"

Rank  Pokémon            Score    Types                  Flavor
----------------------------------------------------------------------------------------------------
1     Slowpoke           0.4123   water/psychic          Incredibly slow and dopey. It takes 5 secon...
2     Lapras             0.3987   water/ice              A gentle soul that can read the minds of pe...
...
```

## Layout

```
what-pokemon-are-you/
├── scripts/
│   ├── fetch_pokemon.py    # PokeAPI → data/pokemon.json (with per-request cache)
│   ├── build_index.py      # sentence-transformers → data/embeddings.npy
│   └── match_cli.py        # cosine similarity CLI matcher
├── data/                   # generated; safe to commit pokemon.json + embeddings.npy
├── requirements.txt
└── .gitignore
```

## Design notes

- **No vector DB.** With ~1000 Pokémon a NumPy matmul is faster than any
  hosted vector store and adds zero infrastructure.
- **Local embeddings.** `all-MiniLM-L6-v2` is free, runs on CPU, and produces
  reproducible vectors so the index can be rebuilt in CI.
- **PokeAPI cache.** Each API response is cached to `data/.cache/` so reruns
  cost nothing and the script is offline-safe after the first run.
