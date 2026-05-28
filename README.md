# What Pokémon Are You?

You fill out a short form — describe your personality in plain English, pick a favorite color, a mood, an environment — and the app matches you to the Pokémon whose vibe is closest to yours. It does this using real semantic embeddings, not a decision tree or random quiz logic. Then an LLM writes a short explanation of *why* you got that result.

Live demo: **[coming soon]**

---

## How it actually works

The core idea is treating this like a search problem. Every Pokémon gets converted into a short personality description (using its Pokédex entries, types, abilities, and an LLM-generated vibe blurb), then embedded into a vector using `sentence-transformers`. Your input gets embedded the same way. Finding your Pokémon is just finding the nearest vector — one matrix multiplication across 1025 Pokémon.

A few things that make the matching better than a typical quiz:

- **LLM-generated personality blurbs** — raw Pokédex text talks about mechanics, not personality. Slowpoke's entry doesn't say "laid-back" — it says its tail getting chewed by Shellder triggers its evolution. So I ran every Pokémon through Groq's Llama model and had it write 2–3 sentences about each one's personality and vibe. This is what the embedding actually matches against.
- **Hybrid scoring** — after the semantic match, type-affinity bonuses kick in based on your color/mood/environment choices. If you pick "the ocean" as your environment, water-type Pokémon get a small score boost on top of the embedding score. This stops generic Pokémon from always winning.
- **LLM explanation** — the top match gets sent to Groq along with your description, and it writes a personalized explanation of why you got that Pokémon. This is essentially a tiny RAG (Retrieval-Augmented Generation) system.

The backend is FastAPI. The frontend is Next.js + Tailwind. Everything is free to run.

---

## Running it locally

You'll need Python 3.10+ and Node 18+.

### 1. Python environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Build the Pokémon database

This hits PokeAPI for every Pokémon and caches the results locally. Takes about 10 minutes the first time, then it's instant on subsequent runs because everything gets cached to `data/.cache/`.

```bash
python scripts/fetch_pokemon.py
```

### 3. Generate personality descriptions (optional but recommended)

This is what makes the matching actually good. For each Pokémon, it calls Groq's free API and gets back a 2–3 sentence personality description. The whole thing takes about 30 minutes and costs nothing — Groq's free tier is generous enough. The results are saved to `data/personalities.json` and the script is resumable, so if it gets interrupted just run it again.

You'll need a free Groq API key from [console.groq.com](https://console.groq.com). Add it to `backend/.env`:

```
GROQ_API_KEY=your_key_here
```

Then run:

```bash
python scripts/enrich_descriptions.py
```

### 4. Build the embedding index

This runs every Pokémon's description through `all-MiniLM-L6-v2` and saves the result as a NumPy matrix. Takes about 1–2 minutes on CPU.

```bash
python scripts/build_index.py
```

If `data/personalities.json` exists it'll use that automatically. If not, it falls back to raw Pokédex text (which still works, just with worse personality matching).

### 5. Test the CLI matcher

Before spinning up the full stack, you can test the matching directly:

```bash
python scripts/match_cli.py "I'm a quiet bookworm who likes rainy days and long naps"
```

You should see a ranked list of Pokémon with similarity scores.

### 6. Run the backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # add your GROQ_API_KEY here
uvicorn main:app --reload
```

The API will be at `http://localhost:8000`. The interactive docs are at `http://localhost:8000/docs` — you can test the `/match` endpoint right from the browser.

### 7. Run the frontend

In a separate terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. The backend needs to be running at the same time.

---

## Evaluating the matching quality

There's a hand-crafted test set at `evals/cases.jsonl` with 25 personality descriptions, each mapped to a few Pokémon that would be reasonable matches. The eval runner measures top-1 and top-5 accuracy.

```bash
# Run against the default 3-model comparison
python evals/run_evals.py

# Single model, see each case's result
python evals/run_evals.py --models sentence-transformers/all-MiniLM-L6-v2 --verbose
```

Results on the baseline (raw Pokédex text only, no personality enrichment):

| Model | Dim | Top-1 | Top-5 | Encode Time |
|---|---|---|---|---|
| all-MiniLM-L6-v2 | 384 | 20% | 40% | 11.5s |
| all-mpnet-base-v2 | 768 | 16% | 40% | 77.6s |
| BAAI/bge-small-en-v1.5 | 384 | 16% | 44% | 23.2s |

The numbers look low, but two things are worth knowing. First, a lot of the "misses" are actually vibe-correct — the eval uses exact Pokémon name matching, so `meloetta-aria` counts as wrong even though it's the same Pokémon as `meloetta`. Second, the bigger model (`mpnet-base-v2`) is 7× slower and actually *worse* on top-1, which is a useful real finding: the bottleneck was the corpus data, not the model.

After running the personality enrichment, qualitative results improve noticeably — "playful trickster" now returns Whimsicott (whose ability is literally called "Prankster"), "loyal protector" returns Growlithe, "loves the ocean" returns water types. The strict-name eval doesn't fully capture this because the acceptable lists are too narrow, but it's noticeably better in practice.

---

## Project structure

```
what-pokemon-are-you/
├── scripts/
│   ├── fetch_pokemon.py        # pulls all Pokémon from PokeAPI, caches locally
│   ├── enrich_descriptions.py  # generates personality blurbs via Groq (one-time)
│   ├── build_index.py          # embeds all descriptions, saves embeddings.npy
│   └── match_cli.py            # test the matcher from the command line
├── evals/
│   ├── cases.jsonl             # 25 hand-written test cases
│   └── run_evals.py            # measures top-1 / top-5 accuracy per model
├── backend/
│   ├── main.py                 # FastAPI app, loads everything once at startup
│   ├── matcher.py              # the actual matching logic (embeddings + type boosts)
│   ├── explainer.py            # calls Groq to generate the "why you got this Pokémon" text
│   ├── type_affinity.py        # maps environment/color/mood → type score bonuses
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   └── src/
│       ├── app/                # Next.js App Router pages
│       ├── components/         # QuizForm, PokemonResult, StatsRadar, TypeBadge, etc.
│       └── lib/                # API client, types, type color map
├── data/                       # generated files (safe to commit)
│   ├── pokemon.json            # cached Pokémon records from PokeAPI
│   ├── personalities.json      # LLM-generated personality blurbs
│   └── embeddings.npy          # the embedding matrix (~1.5MB)
├── requirements.txt            # top-level Python deps for scripts + evals
└── .gitignore
```

---

## Technical decisions worth noting

**No vector database.** With 1025 Pokémon, a vector DB adds deployment complexity for zero performance gain. `embeddings @ query_vec` in NumPy finishes in under a millisecond.

**Hybrid scoring instead of pure embedding.** Pure semantic similarity has a hubness problem — generic Pokémon like Kecleon ("adapts to any environment") end up near the center of the embedding space and match too many queries. Adding small type-affinity bonuses for color/mood/environment pushes the result toward appropriately typed Pokémon when the structured fields are filled in.

**LLM for writing, not for matching.** The LLM runs in two places: once offline to write personality descriptions for the corpus, and once per request to narrate the result. It never makes the actual matching decision — that's entirely the embedding similarity. This keeps the system grounded and fast.

**Model loads once at startup.** The `sentence-transformers` model and the embedding matrix both load when the FastAPI server starts, not per request. A cold start takes a few seconds; after that each match takes about 50ms for the embedding + 1ms for the matrix multiply.

**Groq for the free LLM tier.** Claude and GPT APIs cost money per call. Groq's free tier gives ~14,000 requests/day, which is more than enough for a demo. If `GROQ_API_KEY` isn't set, the backend falls back to returning the Pokémon's raw Pokédex entry as the explanation instead of failing.
