"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import type { MatchRequest } from "@/lib/types";

interface QuizFormProps {
  onSubmit: (req: MatchRequest) => void;
  disabled?: boolean;
}

// Hand-picked vibe options for the structured fields. Free-text would be more
// flexible but dropdowns keep the UX fast and stop people from blanking.
const MOODS = ["Calm", "Energetic", "Curious", "Bold", "Quiet", "Playful", "Determined"];
const ENVIRONMENTS = [
  "The Ocean",
  "The Forest",
  "The Mountains",
  "The City",
  "The Desert",
  "Outer Space",
  "My Room",
];

export function QuizForm({ onSubmit, disabled = false }: QuizFormProps) {
  // Single piece of form state keyed by field name. Simpler than 4 useState calls.
  const [form, setForm] = useState<MatchRequest>({
    description: "",
    color: "",
    mood: "",
    environment: "",
  });

  // Bare minimum validation: backend already enforces 3-1000 chars, just match it.
  const canSubmit = form.description.trim().length >= 3 && !disabled;

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    // Strip empty optional fields so the request body stays clean.
    const payload: MatchRequest = { description: form.description.trim() };
    if (form.color?.trim()) payload.color = form.color.trim();
    if (form.mood?.trim()) payload.mood = form.mood.trim();
    if (form.environment?.trim()) payload.environment = form.environment.trim();
    onSubmit(payload);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-2xl space-y-6 rounded-2xl bg-white p-8 shadow-xl ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
    >
      {/* Free-text description — the main signal the matcher uses. */}
      <div className="space-y-2">
        <label htmlFor="description" className="block text-sm font-semibold text-slate-800 dark:text-slate-200">
          Describe yourself in a few sentences
        </label>
        <textarea
          id="description"
          name="description"
          rows={4}
          required
          minLength={3}
          maxLength={1000}
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          placeholder="e.g. I'm a quiet bookworm who loves rainy days, tea, and long naps..."
          className="w-full resize-none rounded-lg border border-slate-300 bg-white px-4 py-3 text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
        />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {form.description.length} / 1000
        </p>
      </div>

      {/* Optional structured fields — folded into the query blob server-side. */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <label htmlFor="color" className="block text-sm font-semibold text-slate-800 dark:text-slate-200">
            Favorite color
          </label>
          <input
            id="color"
            type="text"
            value={form.color}
            onChange={(e) => setForm({ ...form, color: e.target.value })}
            placeholder="Blue"
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="mood" className="block text-sm font-semibold text-slate-800 dark:text-slate-200">
            Mood
          </label>
          <select
            id="mood"
            value={form.mood}
            onChange={(e) => setForm({ ...form, mood: e.target.value })}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            <option value="">(any)</option>
            {MOODS.map((m) => (
              <option key={m} value={m.toLowerCase()}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label htmlFor="environment" className="block text-sm font-semibold text-slate-800 dark:text-slate-200">
            Environment
          </label>
          <select
            id="environment"
            value={form.environment}
            onChange={(e) => setForm({ ...form, environment: e.target.value })}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            <option value="">(any)</option>
            {ENVIRONMENTS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="group inline-flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-red-500 to-red-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-red-500/30 transition hover:from-red-600 hover:to-red-700 hover:shadow-red-500/40 disabled:cursor-not-allowed disabled:from-slate-400 disabled:to-slate-400 disabled:shadow-none"
      >
        <Sparkles className="h-4 w-4 transition group-hover:rotate-12" />
        Find My Pokémon
      </button>
    </form>
  );
}
