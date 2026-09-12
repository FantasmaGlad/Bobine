"use client";

import React, { useEffect, useRef, useState } from "react";

interface MarqueeTextProps {
  text?: string | null;
  className?: string;
  style?: React.CSSProperties;
  title?: string;
}

/**
 * Composant de défilement horizontal (Marquee) fluide pour les titres de cours :
 * Si le texte dépasse la largeur maximale stricte du conteneur (280px ou colonne de liste),
 * il défile en va-et-vient régulier sans jamais étirer ni déformer la carte ou sa miniature.
 * Si le texte tient dans la largeur, il reste statique.
 */
export default function MarqueeText({ text, className = "", style, title }: MarqueeTextProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const textRef = useRef<HTMLSpanElement | null>(null);
  const [overflowPx, setOverflowPx] = useState(0);
  const displayText = text ?? "";

  useEffect(() => {
    const measure = () => {
      const c = containerRef.current;
      const t = textRef.current;
      if (!c || !t) return;
      // scrollWidth > clientWidth indique un débordement réel
      const diff = t.scrollWidth - c.clientWidth;
      setOverflowPx(diff > 3 ? diff : 0);
    };

    measure();
    // Re-mesure après le montage initial du DOM et au redimensionnement
    const timer = setTimeout(measure, 60);
    window.addEventListener("resize", measure);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", measure);
    };
  }, [displayText]);

  const durationSec = Math.max(5, Math.min(14, overflowPx / 22));

  return (
    <div
      ref={containerRef}
      className={`marquee-track ${overflowPx > 0 ? "marquee-overflowing" : ""} ${className}`}
      title={title ?? (text || undefined)}
      style={{
        ...style,
        ...(overflowPx > 0
          ? ({
              "--marquee-distance": `-${overflowPx + 8}px`,
              "--marquee-duration": `${durationSec}s`,
            } as React.CSSProperties)
          : {}),
      }}
    >
      <span ref={textRef} className="marquee-content">
        {displayText}
      </span>
    </div>
  );
}
