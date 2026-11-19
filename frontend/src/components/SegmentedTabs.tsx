"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useSegmentedIndicator } from "@/components/segmented/useSegmentedIndicator";

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

export default function SegmentedTabs({ tabs, value, onChange, ariaLabel, className = "" }: Props) {
  const { trackRef, scrollerRef, indicator, edge, updateEdge } = useSegmentedIndicator(value, tabs.length);

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
