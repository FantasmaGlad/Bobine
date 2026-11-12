import React from "react";

interface IconProps {
  /** Nom de ligature Material Symbols (ex. "play_arrow", "space_dashboard"). */
  name: string;
  size?: number;
  /** Rempli (bouton principal actif) plutôt qu'en contour. */
  filled?: boolean;
  weight?: 400 | 500 | 600 | 700;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}

/** Icône Material Symbols (police variable embarquée, déclarée dans layout.tsx). */
export default function Icon({ name, size = 20, filled = false, weight = 400, color, className, style }: IconProps) {
  return (
    <span
      className={`material-symbols-outlined${className ? ` ${className}` : ""}`}
      aria-hidden="true"
      style={{
        fontSize: size,
        color,
        fontVariationSettings: `'FILL' ${filled ? 1 : 0}, 'wght' ${weight}, 'GRAD' 0, 'opsz' ${size}`,
        ...style,
      }}
    >
      {name}
    </span>
  );
}
