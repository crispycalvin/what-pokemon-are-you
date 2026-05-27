# syntax=docker/dockerfile:1
# Slim Python image; 3.12 has the best compatibility with sentence-transformers
# and torch wheels as of 2026-05.
FROM python:3.12-slim

# Standard hardening / cache settings for Python in Docker.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.huggingface \
    DATA_DIR=/app/data

WORKDIR /app

# Install Python deps in their own layer so code edits don't bust the cache.
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Pre-download the embedding model into the image so the first request
# after deploy is fast (no ~80MB cold download on the first user).
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# App code + pre-built index. data/ must contain pokemon.json, embeddings.npy,
# pokemon_names.json — built once locally via scripts/ and committed to the repo.
COPY backend/ /app/backend/
COPY data/ /app/data/

WORKDIR /app/backend

# Railway / Fly inject PORT; default to 8000 for local docker runs.
ENV PORT=8000
EXPOSE 8000

# Single worker is correct here — the embedding model + index live in RAM and
# we don't want N copies. Tune up only if traffic justifies it.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
