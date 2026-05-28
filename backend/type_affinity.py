"""
Type-affinity bonuses for hybrid scoring.

Maps user-supplied structured fields (environment, color, mood) to
Pokémon type → bonus magnitude pairs. These bonuses are added on top of
cosine similarity scores so structured signals reinforce — but never
completely override — the semantic embedding match.

Bonus magnitudes are calibrated against enriched-corpus scores (~0.3-0.6).
A primary-type bonus of 0.08 is meaningful (breaks ties, surfaces correct
Pokémon) without bulldozing a clearly better semantic match.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Affinity tables
# ---------------------------------------------------------------------------

# Each sub-dict maps a canonicalized field value (lowercase, stripped) to
# a {type_name: bonus} dict. Types not listed get 0
ENVIRONMENT_AFFINITIES: dict[str, dict[str, float]] = {
    "the ocean":      {"water": 0.09, "ice": 0.05},
    "the forest":     {"grass": 0.09, "bug": 0.06, "fairy": 0.04},
    "the mountains":  {"rock": 0.09, "ground": 0.06, "flying": 0.05},
    "the desert":     {"ground": 0.09, "fire": 0.06, "rock": 0.05},
    "the city":       {"normal": 0.06, "electric": 0.06, "dark": 0.05, "steel": 0.04},
    "outer space":    {"psychic": 0.09, "dragon": 0.06, "steel": 0.05},
    "my room":        {"normal": 0.06, "psychic": 0.06, "fairy": 0.04},
}

COLOR_AFFINITIES: dict[str, dict[str, float]] = {
    "red":    {"fire": 0.07, "fighting": 0.06, "dragon": 0.04},
    "blue":   {"water": 0.07, "ice": 0.05, "flying": 0.04},
    "green":  {"grass": 0.07, "bug": 0.05, "dragon": 0.04},
    "yellow": {"electric": 0.09, "normal": 0.04},
    "purple": {"poison": 0.07, "psychic": 0.06, "ghost": 0.05},
    "pink":   {"fairy": 0.09, "psychic": 0.04, "normal": 0.03},
    "black":  {"dark": 0.09, "ghost": 0.07},
    "white":  {"ice": 0.07, "fairy": 0.06, "steel": 0.05},
    "brown":  {"ground": 0.07, "rock": 0.06, "normal": 0.04},
    "orange": {"fire": 0.07, "fighting": 0.04},
    "grey":   {"steel": 0.07, "rock": 0.05, "normal": 0.04},
    "gray":   {"steel": 0.07, "rock": 0.05, "normal": 0.04},
}

MOOD_AFFINITIES: dict[str, dict[str, float]] = {
    "calm":        {"water": 0.06, "grass": 0.05, "fairy": 0.04, "psychic": 0.04},
    "energetic":   {"electric": 0.09, "fire": 0.06, "fighting": 0.05},
    "bold":        {"fighting": 0.07, "dragon": 0.06, "dark": 0.05},
    "quiet":       {"ghost": 0.09, "psychic": 0.06, "dark": 0.04},
    "curious":     {"psychic": 0.07, "normal": 0.05, "fairy": 0.04},
    "playful":     {"fairy": 0.07, "normal": 0.06, "electric": 0.05},
    "determined":  {"fighting": 0.07, "fire": 0.05, "dragon": 0.05},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_type_bonus(
    pokemon_types: list[str],
    *,
    environment: str | None = None,
    color: str | None = None,
    mood: str | None = None,
) -> float:
    """Return the total type-affinity bonus for a Pokémon given structured fields.

    pokemon_types: list of type strings from the Pokémon record (already lowercase).
    Returns a float bonus to add to the raw cosine similarity score.
    """
    bonus = 0.0
    type_set = {t.lower() for t in pokemon_types}

    for field_value, table in (
        (environment, ENVIRONMENT_AFFINITIES),
        (color, COLOR_AFFINITIES),
        (mood, MOOD_AFFINITIES),
    ):
        if not field_value:
            continue
        key = field_value.strip().lower()
        affinities = table.get(key, {})
        # Sum bonuses for each type the Pokémon actually has
        for ptype in type_set:
            bonus += affinities.get(ptype, 0.0)

    return bonus
