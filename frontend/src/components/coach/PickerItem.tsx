"use client";

import React from "react";
import Icon from "@/components/Icon";

export default function PickerItem({ index, title, meta, onLaunch }: { index: number; title: string; meta: React.ReactNode; onLaunch: () => void }) {
  return (
    <button
      className="coach-course-item olc-press olc-card-hover olc-anim-in"
      style={{ animationDelay: `${Math.min(index, 8) * 30}ms` }}
      onClick={onLaunch}
    >
      <span className="coach-course-item-accent" style={{ background: "var(--accent-primary)" }} />
      <span className="coach-course-item-body">
        <span className="coach-course-item-title">{title}</span>
        <span className="coach-course-item-meta">
          {meta}
        </span>
      </span>
      <Icon name="play_circle" size={22} />
    </button>
  );
}
