"use client";

import Image from "next/image";
import { RefreshCw, Sparkles } from "lucide-react";
import type { MatchResponse, PokemonResult as PokemonResultType } from "@/lib/types";
import { typeColor, typeGradient } from "@/lib/typeColors";
import { TypeBadge } from "./TypeBadge";
import { StatsRadar } from "./StatsRadar";

interface PokemonResultProps {
  result: MatchResponse;
  onReset: () => void;
}

// Title-case a Pokémon name (handles hyphenated forms like "mr-mime")
function prettyName(name: string): string {
  return name
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

// Top-level result view: hero card with the matched Pokémon + explanation,
// then a row of runners-up underneath
export function PokemonResult({ result, onReset }: PokemonResultProps) {
  const { pokemon, explanation, runners_up, llm_enabled } = result;
  const primaryColor = typeColor(pokemon.types[0] ?? "normal");

  return (
    <div className="w-full max-w-4xl space-y-6 animate-fade-in">
      {/* Hero card — the showpiece */}
      <div
        className="overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
        style={{ background: typeGradient(pokemon.types) }}
      >
        <div className="grid gap-6 p-8 md:grid-cols-[1fr_1.2fr] md:gap-10">
          {/* Sprite + name side */}
          <div className="flex flex-col items-center justify-center text-center">
            <p className="text-sm font-medium uppercase tracking-widest text-slate-600">
              You are
            </p>
            {pokemon.sprite_url ? (
              <div className="relative my-2 h-56 w-56 md:h-64 md:w-64">
                <Image
                  src={pokemon.sprite_url}
                  alt={pokemon.name}
                  fill
                  sizes="256px"
                  className="object-contain drop-shadow-xl"
                  priority
                />
              </div>
            ) : (
              <div className="my-2 flex h-56 w-56 items-center justify-center rounded-full bg-slate-200 text-slate-500">
                no sprite
              </div>
            )}
            <h1 className="text-4xl font-bold text-slate-900">{prettyName(pokemon.name)}</h1>
            <p className="mt-1 text-sm font-mono text-slate-600">
              #{String(pokemon.id).padStart(3, "0")}
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {pokemon.types.map((t) => (
                <TypeBadge key={t} type={t} />
              ))}
            </div>
          </div>

          {/* Stats + explanation side */}
          <div className="space-y-5 rounded-xl bg-white/80 p-6 backdrop-blur dark:bg-slate-900/80">
            <div>
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-500">
                <Sparkles className="h-3.5 w-3.5" />
                Why you?
              </h2>
              <p className="text-base leading-relaxed text-slate-800 dark:text-slate-100">
                {explanation}
              </p>
              {!llm_enabled && (
                <p className="mt-2 text-xs italic text-slate-400">
                  (LLM explanations disabled — set GROQ_API_KEY for richer reasoning.)
                </p>
              )}
            </div>

            <div>
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-500">
                Base stats
              </h2>
              <StatsRadar stats={pokemon.stats} color={primaryColor} />
            </div>

            <p className="text-xs text-slate-500">
              Similarity score: <span className="font-mono">{pokemon.score.toFixed(3)}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Runners-up — the "you're also a bit like..." section */}
      {runners_up.length > 0 && (
        <div className="rounded-2xl bg-white p-6 shadow-lg ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
            You&apos;re also a bit like...
          </h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {runners_up.map((runner) => (
              <RunnerUpCard key={runner.id} pokemon={runner} />
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-center">
        <button
          onClick={onReset}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-slate-900 dark:bg-slate-700 dark:hover:bg-slate-600"
        >
          <RefreshCw className="h-4 w-4" />
          Try Again
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Runners-up card
// ---------------------------------------------------------------------------

function RunnerUpCard({ pokemon }: { pokemon: PokemonResultType }) {
  return (
    <div
      className="flex flex-col items-center gap-2 rounded-xl p-3 text-center transition hover:scale-105"
      style={{ background: typeGradient(pokemon.types) }}
    >
      {pokemon.sprite_url ? (
        <div className="relative h-20 w-20">
          <Image
            src={pokemon.sprite_url}
            alt={pokemon.name}
            fill
            sizes="80px"
            className="object-contain"
          />
        </div>
      ) : (
        <div className="h-20 w-20 rounded-full bg-slate-200" />
      )}
      <p className="text-sm font-semibold text-slate-800">{prettyName(pokemon.name)}</p>
      <p className="text-xs font-mono text-slate-600">{pokemon.score.toFixed(3)}</p>
    </div>
  );
}
