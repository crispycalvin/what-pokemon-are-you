"""
LLM-generated explanation of why a user matches a given Pokémon.

Calls Groq's free-tier API with the user's self-description + the matched
Pokémon's Pokédex entry. Falls back to a deterministic, flavor-text-based
explanation if no GROQ_API_KEY is set so the backend stays usable offline
and during local dev.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from groq import Groq

logger = logging.getLogger(__name__)

# Llama-3.1 8b on Groq: fast, free tier, plenty smart for a 2-3 sentence blurb.
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

SYSTEM_PROMPT = (
    "You are a playful but thoughtful Pokémon expert. Given a person's "
    "self-description and the Pokémon they were matched to (via semantic "
    "similarity), write a 2-3 sentence explanation of why this Pokémon "
    "suits them. Reference specific details from both their description "
    "and the Pokémon's lore. Be warm and slightly witty. Do not invent "
    "Pokémon facts that aren't in the Pokédex entry provided."
)


class Explainer:
    """Wraps the Groq client + prompt construction with a sane fallback."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        # Only construct a client if we actually have credentials.
        key = api_key or os.getenv("GROQ_API_KEY")
        self._client: Groq | None = Groq(api_key=key) if key else None
        if self._client is None:
            logger.warning(
                "GROQ_API_KEY not set — Explainer will use deterministic fallback."
            )

    @property
    def llm_enabled(self) -> bool:
        # Surfaced so callers / health checks can see whether real LLM calls are happening.
        return self._client is not None

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    @staticmethod
    def _user_prompt(user_description: str, pokemon: dict[str, Any]) -> str:
        # Stuff the Pokémon's full context into the user message so the LLM
        # can ground its reasoning without a separate retrieval step.
        types = ", ".join(pokemon.get("types", []))
        abilities = ", ".join(pokemon.get("abilities", []))
        flavor = pokemon.get("flavor_text", "").strip() or "(no Pokédex entry available)"
        name = pokemon.get("name", "").replace("-", " ").title()

        return (
            f"Person's self-description:\n\"{user_description.strip()}\"\n\n"
            f"Matched Pokémon: {name}\n"
            f"Types: {types}\n"
            f"Abilities: {abilities}\n"
            f"Pokédex entry: {flavor}\n\n"
            "Explain why this person matches this Pokémon in 2-3 sentences."
        )

    # ------------------------------------------------------------------
    # Explanation generation
    # ------------------------------------------------------------------

    def explain(self, user_description: str, pokemon: dict[str, Any]) -> str:
        # No API key → use the deterministic fallback.
        if self._client is None:
            return self._fallback(user_description, pokemon)

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._user_prompt(user_description, pokemon)},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            content = response.choices[0].message.content
            return (content or "").strip() or self._fallback(user_description, pokemon)
        except Exception as exc:
            # Network blip, rate limit, etc. — don't break the user's request.
            logger.exception("Groq call failed; using fallback explanation. %s", exc)
            return self._fallback(user_description, pokemon)

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback(user_description: str, pokemon: dict[str, Any]) -> str:
        # Plain-text explanation derived from the matched Pokémon's own Pokédex entry.
        name = pokemon.get("name", "your match").replace("-", " ").title()
        types = " / ".join(pokemon.get("types", [])) or "mysterious"
        flavor = pokemon.get("flavor_text", "").strip()

        intro = f"You match best with {name}, a {types}-type Pokémon."
        if flavor:
            return f"{intro} From the Pokédex: \"{flavor}\""
        return intro
