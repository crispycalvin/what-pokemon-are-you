import { typeColor } from "@/lib/typeColors";

interface TypeBadgeProps {
  type: string;
}

// Small color-coded pill for a single Pokémon type.
export function TypeBadge({ type }: TypeBadgeProps) {
  return (
    <span
      className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white shadow-sm"
      style={{ backgroundColor: typeColor(type) }}
    >
      {type}
    </span>
  );
}
