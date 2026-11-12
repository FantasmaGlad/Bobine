import React from "react";

interface IconProps {
  name: string;
  size?: number;
  filled?: boolean;
  weight?: 400 | 500 | 600 | 700;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}

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
