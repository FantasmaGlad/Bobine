"use client";

import React, { useEffect, useRef, useState } from "react";

const watchers = new Map<Element, () => void>();
let sizeObserver: ResizeObserver | null = null;

function watchSize(elements: Element[], onResize: () => void): () => void {
  sizeObserver ??= new ResizeObserver((entries) => {
    for (const entry of entries) watchers.get(entry.target)?.();
  });
  for (const element of elements) {
    watchers.set(element, onResize);
    sizeObserver.observe(element);
  }
  return () => {
    for (const element of elements) {
      watchers.delete(element);
      sizeObserver?.unobserve(element);
    }
  };
}

interface MarqueeTextProps {
  text?: string | null;
  className?: string;
  style?: React.CSSProperties;
  title?: string;
}

export default function MarqueeText({ text, className = "", style, title }: MarqueeTextProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const textRef = useRef<HTMLSpanElement | null>(null);
  const [overflowPx, setOverflowPx] = useState(0);
  const displayText = text ?? "";

  useEffect(() => {
    const c = containerRef.current;
    const t = textRef.current;
    if (!c || !t) return;
    return watchSize([c, t], () => {
      const diff = t.scrollWidth - c.clientWidth;
      setOverflowPx(diff > 3 ? diff : 0);
    });
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
