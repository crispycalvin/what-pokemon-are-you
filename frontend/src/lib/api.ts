import type { MatchRequest, MatchResponse } from "./types";

// Backend URL injected at build time. NEXT_PUBLIC_ vars are exposed to the browser.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function matchPokemon(req: MatchRequest): Promise<MatchResponse> {
  // POST the user's description + structured fields to /match.
  const response = await fetch(`${API_URL}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  // FastAPI returns JSON error detail on 4xx/5xx; surface it for nicer UX.
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // Body wasn't JSON; keep the generic message.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<MatchResponse>;
}
