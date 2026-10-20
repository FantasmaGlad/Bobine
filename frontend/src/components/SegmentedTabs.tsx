"use client";

import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";

export interface SegmentedTab {
  id: string;
  label: string;
  icon?: string;
  count?: number;
}

interface Props {
  tabs: SegmentedTab[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  className?: string;
}

/**
 * Barre de sections segmentée avec un indicateur UNIQUE qui glisse d'un onglet à l'autre (transform +
 * largeur mesurée, pas de repeinture de chaque bouton). Défile horizontalement sur petit écran et garde
 * l'onglet actif visible ; flèches gauche/droite entre onglets. Sur téléphone, 3 onglets au plus sont affichés
 * (le suivant dépasse un peu : invitation à glisser) et le défilement s'« accroche » sur l'onglet visé.
 */
export default function SegmentedTabs({ tabs, value, onChange, ariaLabel, className = "" }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);
  // Bord atteint par le défilement : sert aux fondus d'indice « il y a d'autres onglets, glissez ».
  const [edge, setEdge] = useState<"none" | "start" | "middle" | "end">("none");

  const updateEdge = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    if (el.scrollWidth <= el.clientWidth + 1) setEdge("none");
    else if (el.scrollLeft <= 2) setEdge("start");
    else if (el.scrollLeft >= el.scrollWidth - el.clientWidth - 2) setEdge("end");
    else setEdge("middle");
  }, []);

  const measure = useCallback(() => {
    const track = trackRef.current;
    const active = track?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    if (!track || !active) return;
    setIndicator({ left: active.offsetLeft, width: active.offsetWidth });
    active.scrollIntoView({ inline: "center", block: "nearest" });
    updateEdge();
  }, [updateEdge]);

  useLayoutEffect(() => {
    measure();
  }, [measure, value, tabs.length]);

  useEffect(() => {
    const track = trackRef.current;
    if (!track || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(track);
    document.fonts?.ready.then(measure).catch(() => undefined);
    return () => observer.disconnect();
  }, [measure]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const index = tabs.findIndex((tab) => tab.id === value);
    const next = tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    if (next) {
      event.preventDefault();
      onChange(next.id);
      requestAnimationFrame(() => trackRef.current?.querySelector<HTMLElement>(`[data-tab="${next.id}"]`)?.focus());
    }
  };

  return (
    <div
      ref={scrollerRef}
      className={`seg ${tabs.length > 3 ? "seg--many" : ""} ${className}`}
      data-edge={edge}
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      onScroll={updateEdge}
    >
      <div className="seg-track" ref={trackRef}>
        {indicator && (
          <span className="seg-indicator" aria-hidden="true" style={{ width: indicator.width, transform: `translateX(${indicator.left}px)` }} />
        )}
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            data-tab={tab.id}
            aria-selected={value === tab.id}
            tabIndex={value === tab.id ? 0 : -1}
            className={`seg-btn olc-press ${value === tab.id ? "active" : ""}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.icon && <Icon name={tab.icon} size={16} />}
            <span>{tab.label}</span>
            {tab.count !== undefined && <span className="rl-tab-count">{tab.count}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
