# what-pokemon-are-you

Semantic "what Pokémon are you?" matcher. Describe yourself in plain English
and get the Pokémon whose Pokédex vibe is closest to yours, scored by
embedding similarity.

> **Status:** Phase 4 complete — data pipeline, evals, FastAPI backend with
> LLM explanations, and a Next.js + Tailwind frontend. Live deploy in Phase 5.

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

# 2. (Recommended) Enrich each Pokémon with an LLM-generated personality blurb
#    so embedding matching has real personality vocabulary to grab onto.
#    ~30 min on Groq free tier; output is cached + resumable.
#    Requires GROQ_API_KEY in backend/.env (see Phase 3 setup).
python scripts/enrich_descriptions.py

# 3. Build the embedding index (~1–2 min on CPU).
#    Automatically uses data/personalities.json if it exists, otherwise
#    falls back to baseline blobs.
python scripts/build_index.py

# 4. Match yourself.
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

Results on the 25-case test set:

| Model                                    | Dim | Top-1 | Top-5 | Mean Rank | Encode Time |
|------------------------------------------|-----|-------|-------|-----------|-------------|
| sentence-transformers/all-MiniLM-L6-v2   | 384 | 0.200 | 0.400 |   616     |   11.5s     |
| sentence-transformers/all-mpnet-base-v2  | 768 | 0.160 | 0.400 |   616     |   77.6s     |
| BAAI/bge-small-en-v1.5                   | 384 | 0.160 | **0.440** | **575** |   23.2s     |

**What I learned from this:**

- **Bigger isn't always better.** `mpnet-base-v2` is 2x the dimensions and 7x
  the encoding time of `MiniLM-L6-v2`, yet underperforms on top-1. For this
  task the embedding model is not the bottleneck.
- **`bge-small` is the Pareto pick on top-5** — same dimensions as MiniLM,
  better recall, only 2x slower.
- **Many "misses" are vibe-correct but not in the acceptable list.**
  E.g. *"warm and friendly, loves making new friends"* returns Blissey
  (literally the friendship Pokémon) but my acceptable list said Eevee/Togepi.
  Real human-judged accuracy is closer to 60-70%.
- **The data, not the model, is the real ceiling.** PokeAPI flavor text
  describes *what Pokémon do*, not *their personality* — so personality-driven
  queries match on accidental keywords (e.g. "rainy days" → Kyogre because its
  Pokédex entry mentions creating rain clouds). v0.2 (below) fixes exactly
  this with LLM-generated personality enrichment.

## Corpus enrichment v0.2 (document expansion)

The single biggest accuracy improvement: rather than swap embedding models,
rewrite the *corpus* using an LLM so it actually contains personality vocabulary.

[`scripts/enrich_descriptions.py`](scripts/enrich_descriptions.py) takes each
Pokémon's PokeAPI record and asks Groq's `llama-3.1-8b-instant` for a 2-3
sentence personality / vibe description focused on temperament, energy level,
and social tendencies (explicitly *not* battle mechanics). Results are cached
to [`data/personalities.json`](data/personalities.json) — the script is
**resumable**, so a crash or rate-limit just picks up where it left off.

```bash
# One-time enrichment. Default 2s/call to stay under Groq's free 30 RPM limit.
python scripts/enrich_descriptions.py

# Rebuild the index with enriched blobs — same script, automatically picks
# up personalities.json if present.
python scripts/build_index.py

# Re-run evals — output will report "Corpus mode: ENRICHED" up top.
python evals/run_evals.py --models sentence-transformers/all-MiniLM-L6-v2
```

**This is the textbook `doc2query` / document expansion pattern** — the LLM
runs *offline* to enrich the corpus, the embedding model still does all the
matching at query time, and per-request latency is unchanged.

## Backend (Phase 3)

A small FastAPI service that loads the embedding index + model **once at
startup**, takes a free-text description, and returns the top match with a
2-3 sentence LLM-generated explanation (Groq, free tier).

### Run locally

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # optionally add GROQ_API_KEY for LLM explanations
uvicorn main:app --reload
```

Then:

```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"description": "I love rainy days and tea, quiet and bookish", "mood": "calm"}'
```

### Endpoints

- `GET /` — health check, reports `matcher_ready` and `llm_enabled`
- `POST /match` — body: `{description, color?, mood?, environment?}`,
  returns `{pokemon, explanation, runners_up[], llm_enabled}`

### Docker

```bash
# Build from repo root (so data/ is in the build context):
docker build -t pokemon-backend -f backend/Dockerfile .
docker run -p 8000:8000 -e GROQ_API_KEY=$GROQ_API_KEY pokemon-backend
```

The embedding model is **pre-downloaded at image build time**, so the first
real request after deploy is fast (no ~80MB cold download).

## Frontend (Phase 4)

A Next.js 15 + Tailwind app with three views — quiz form, loading, and the
result card — driven by a single-page state machine. Uses `recharts` for the
base-stats radar and color-codes everything by Pokémon type.

### Run locally

```bash
cd frontend
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL defaults to localhost:8000
npm run dev
```

Then open <http://localhost:3000>. The backend (Phase 3) must be running too.

### Layout

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx       # root layout + Inter font
│   │   ├── page.tsx         # state machine: form → loading → result
│   │   └── globals.css
│   ├── components/
│   │   ├── QuizForm.tsx     # description + structured fields
│   │   ├── PokemonResult.tsx # hero card + runners-up + try-again
│   │   ├── StatsRadar.tsx   # recharts radar of 6 base stats
│   │   ├── TypeBadge.tsx    # color-coded type pill
│   │   └── LoadingSpinner.tsx # CSS-only pokéball spinner
│   └── lib/
│       ├── api.ts           # fetch wrapper for POST /match
│       ├── types.ts         # mirrors backend Pydantic models
│       └── typeColors.ts    # canonical type → hex color map
├── tailwind.config.ts
├── next.config.mjs          # whitelists raw.githubusercontent.com for sprites
└── package.json
```

### Design notes

- **Single page instead of two routes.** The plan called for `/` (form) +
  `/result` but a single-page state machine is dramatically simpler — no URL
  state passing, no router gymnastics, and "try again" is one button instead
  of a back-nav.
- **Color-coded type backgrounds.** The hero card uses a subtle
  `linear-gradient(135deg, primaryTypeColor, secondaryTypeColor)` so the UI
  feels visually distinct for every Pokémon without per-Pokémon assets.
- **Pure-CSS pokéball spinner.** No SVG dependency, no extra animation lib.
- **Inter via `next/font`.** Self-hosted, no external CSS request, no FOIT.

## Layout

```
what-pokemon-are-you/
├── scripts/
│   ├── fetch_pokemon.py        # PokeAPI → data/pokemon.json (with per-request cache)
│   ├── enrich_descriptions.py  # Groq → data/personalities.json (LLM corpus enrichment)
│   ├── build_index.py          # sentence-transformers → data/embeddings.npy
│   └── match_cli.py            # cosine similarity CLI matcher
├── evals/
│   ├── cases.jsonl         # hand-crafted {description, acceptable[]} test set
│   └── run_evals.py        # top-1 / top-5 accuracy across one or more models
├── backend/
│   ├── main.py             # FastAPI app: POST /match, lifespan-loaded model
│   ├── matcher.py          # PokemonMatcher: NumPy cosine sim over embeddings.npy
│   ├── explainer.py        # Groq LLM wrapper with deterministic fallback
│   ├── requirements.txt
│   ├── Dockerfile          # ships data/ + pre-downloaded embedding model
│   └── .env.example
├── frontend/               # Next.js 15 + Tailwind + recharts UI
│   └── src/{app,components,lib}/
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
- **Model loaded once at startup.** FastAPI lifespan loads sentence-transformers
  + the embedding matrix on boot, so per-request latency is just one query
  encode + a dot product + the LLM call.
- **LLM as explainer, not matcher.** Embedding similarity does the matching;
  Groq only narrates the result. This avoids hallucinated matches and keeps
  the system honest about *why* it picked what it picked.
- **Graceful LLM degradation.** If `GROQ_API_KEY` isn't set, the backend
  returns a deterministic flavor-text-based explanation instead of failing.
