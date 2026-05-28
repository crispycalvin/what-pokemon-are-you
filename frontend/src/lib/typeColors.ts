// Canonical Pokémon type → color mapping. Hex values match the long-standing
// community palette used on Bulbapedia / official media

export const TYPE_COLORS: Record<string, string> = {
  normal: "#A8A878",
  fire: "#F08030",
  water: "#6890F0",
  electric: "#F8D030",
  grass: "#78C850",
  ice: "#98D8D8",
  fighting: "#C03028",
  poison: "#A040A0",
  ground: "#E0C068",
  flying: "#A890F0",
  psychic: "#F85888",
  bug: "#A8B820",
  rock: "#B8A038",
  ghost: "#705898",
  dragon: "#7038F8",
  dark: "#705848",
  steel: "#B8B8D0",
  fairy: "#EE99AC",
};

// Fallback for unknown types (e.g. typos, future generations)
const FALLBACK_COLOR = "#68A090";

export function typeColor(type: string): string {
  return TYPE_COLORS[type.toLowerCase()] ?? FALLBACK_COLOR;
}

// Returns a CSS gradient string keyed off the Pokémon's primary (and optional
// secondary) types. Used as a soft background behind the sprite
export function typeGradient(types: string[]): string {
  if (types.length === 0) return `linear-gradient(135deg, #e5e7eb, #f3f4f6)`;
  const primary = typeColor(types[0]);
  const secondary = types[1] ? typeColor(types[1]) : primary;
  return `linear-gradient(135deg, ${primary}33, ${secondary}33)`;
}
