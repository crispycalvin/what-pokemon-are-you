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

## Evaluation

A hand-crafted test set in [evals/cases.jsonl](evals/cases.jsonl) maps 25
self-descriptions to 4–7 acceptable Pokémon each. The runner re-encodes the
whole Pokédex with each candidate model in memory (without overwriting the
committed index) and reports top-1 / top-5 accuracy plus mean rank.

```bash
# Run against the default 3-model comparison (downloads ~500MB of models on first run).
python evals/run_evals.py

# Single model, with per-case PASS/MISS output.
python evals/run_evals.py --models sentence-transformers/all-MiniLM-L6-v2 --verbose
```

Sample output shape (fill in real numbers after running):

| Model                                    | Dim | Top-1 | Top-5 | Mean Rank |
|------------------------------------------|-----|-------|-------|-----------|
| sentence-transformers/all-MiniLM-L6-v2   | 384 |   ?   |   ?   |     ?     |
| sentence-transformers/all-mpnet-base-v2  | 768 |   ?   |   ?   |     ?     |
| BAAI/bge-small-en-v1.5                   | 384 |   ?   |   ?   |     ?     |

The acceptable-list approach matters here — Pokémon "vibe matching" is
genuinely fuzzy, so single-answer accuracy would be misleading.

## Layout

```
what-pokemon-are-you/
├── scripts/
│   ├── fetch_pokemon.py    # PokeAPI → data/pokemon.json (with per-request cache)
│   ├── build_index.py      # sentence-transformers → data/embeddings.npy
│   └── match_cli.py        # cosine similarity CLI matcher
├── evals/
│   ├── cases.jsonl         # hand-crafted {description, acceptable[]} test set
│   └── run_evals.py        # top-1 / top-5 accuracy across one or more models
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
