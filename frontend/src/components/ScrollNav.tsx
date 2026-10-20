"use client";

import React, { Children, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

interface Props {
  children: React.ReactNode;
  className?: string;
}

/**
 * Barre de choix segmentée (`.view-toggle`) à défilement horizontal pour petit écran : au plus 3 choix
 * visibles, le suivant dépasse (invitation à glisser), fondus aux bords et accroche collante (scroll-snap)
 * sur le choix visé. Le choix actif (`.active`) est ramené au centre. Mise en forme : `.scroll-nav` dans globals.css.
 */
export default function ScrollNav({ children, className = "" }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [edge, setEdge] = useState<"none" | "start" | "middle" | "end">("none");
  const count = Children.toArray(children).length;

  const updateEdge = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    if (el.scrollWidth <= el.clientWidth + 1) setEdge("none");
    else if (el.scrollLeft <= 2) setEdge("start");
    else if (el.scrollLeft >= el.scrollWidth - el.clientWidth - 2) setEdge("end");
    else setEdge("middle");
  }, []);

  useLayoutEffect(() => {
    ref.current?.querySelector<HTMLElement>(".active")?.scrollIntoView({ inline: "center", block: "nearest" });
    updateEdge();
  });

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(updateEdge);
    observer.observe(el);
    return () => observer.disconnect();
  }, [updateEdge]);

  return (
    <div ref={ref} className={`view-toggle scroll-nav ${count >= 3 ? "scroll-nav--many" : ""} ${className}`} data-edge={edge} onScroll={updateEdge}>
      {children}
    </div>
  );
}
