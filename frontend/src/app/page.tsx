"use client";

import { useState } from "react";
import { AlertCircle } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PokemonResult } from "@/components/PokemonResult";
import { QuizForm } from "@/components/QuizForm";
import { matchPokemon } from "@/lib/api";
import type { MatchRequest, MatchResponse, ViewState } from "@/lib/types";

// Single-page state machine: form → loading → (result | error) → back to form.
// Simpler + better UX than a multi-route app for a quiz that needs the form
// state alongside the result.
export default function Home() {
  const [view, setView] = useState<ViewState>("form");
  const [result, setResult] = useState<MatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(req: MatchRequest) {
    setView("loading");
    setError(null);
    try {
      const response = await matchPokemon(req);
      setResult(response);
      setView("result");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Something went wrong.";
      setError(message);
      setView("error");
    }
  }

  function handleReset() {
    setView("form");
    setResult(null);
    setError(null);
  }

  return (
    <main className="flex min-h-screen flex-col items-center px-4 py-12 sm:py-16">
      {/* Hero — only shown on the form + loading views */}
      {view !== "result" && (
        <header className="mb-12 max-w-3xl text-center animate-fade-in">
          <h1 className="pokemon-title text-5xl sm:text-7xl">
            What Pok&eacute;mon Are You?
          </h1>
        </header>
      )}

      {/* State-driven body */}
      {view === "form" && <QuizForm onSubmit={handleSubmit} />}
      {view === "loading" && <LoadingSpinner />}
      {view === "result" && result && <PokemonResult result={result} onReset={handleReset} />}
      {view === "error" && (
        <div className="w-full max-w-lg rounded-xl bg-red-50 p-6 ring-1 ring-red-200 dark:bg-red-950/40 dark:ring-red-900">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" />
            <div className="flex-1 space-y-3">
              <h2 className="text-sm font-semibold text-red-900 dark:text-red-200">
                Couldn&apos;t reach the backend
              </h2>
              <p className="text-sm text-red-800 dark:text-red-300">{error}</p>
              <button
                onClick={handleReset}
                className="inline-flex items-center rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-red-700"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="mt-16 text-xs text-slate-300/80">
        <a
          href="https://github.com/crispycalvin/what-pokemon-are-you"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-white"
        >
          Source on GitHub
        </a>
      </footer>
    </main>
  );
}
