// TypeScript mirror of the backend's Pydantic models. Keep in sync with
// backend/main.py (MatchRequest / MatchResponse / PokemonResult).

export interface MatchRequest {
  description: string;
  color?: string;
  mood?: string;
  environment?: string;
}

export interface PokemonResult {
  id: number;
  name: string;
  sprite_url: string | null;
  types: string[];
  stats: Record<string, number>;
  score: number;
}

export interface MatchResponse {
  pokemon: PokemonResult;
  explanation: string;
  runners_up: PokemonResult[];
  llm_enabled: boolean;
}

// View states for the main page state machine.
export type ViewState = "form" | "loading" | "result" | "error";
