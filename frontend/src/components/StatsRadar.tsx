"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

interface StatsRadarProps {
  stats: Record<string, number>;
  color: string;
}

// Canonical order + display labels for the six base stats every Pokémon has.
const STAT_ORDER: Array<{ key: string; label: string }> = [
  { key: "hp", label: "HP" },
  { key: "attack", label: "ATK" },
  { key: "defense", label: "DEF" },
  { key: "special-attack", label: "SP.ATK" },
  { key: "special-defense", label: "SP.DEF" },
  { key: "speed", label: "SPD" },
];

// Radar chart of base stats normalized to a 0-200 scale (covers all but extreme
// outliers, keeps the chart readable across legendaries and starters alike).
export function StatsRadar({ stats, color }: StatsRadarProps) {
  const data = STAT_ORDER.map(({ key, label }) => ({
    stat: label,
    value: stats[key] ?? 0,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#cbd5e1" />
          <PolarAngleAxis
            dataKey="stat"
            tick={{ fill: "#475569", fontSize: 12, fontWeight: 600 }}
          />
          <PolarRadiusAxis domain={[0, 200]} tick={false} axisLine={false} />
          <Radar
            name="Stats"
            dataKey="value"
            stroke={color}
            fill={color}
            fillOpacity={0.4}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
