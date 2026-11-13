"use client";

import React from "react";

import Icon from "@/components/Icon";

import type { DragPayload } from "./media";
import type { ScheduleDrag } from "./useDrag";

interface Props {
  payload: DragPayload;
  thumb: string | null;
  fallbackIcon: string;
  duration: string;
  title: React.ReactNode;
  meta?: React.ReactNode;
  isMobile: boolean;
  drag: ScheduleDrag;
  onPick?: () => void;
}

export default function PickerCard({ payload, thumb, fallbackIcon, duration, title, meta, isMobile, drag, onPick }: Props) {
  const interactive = onPick
    ? {
        role: "button",
        tabIndex: 0,
        onClick: onPick,
        onKeyDown: (e: React.KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onPick();
          }
        },
      }
    : {};
  return (
    <div
      className={`picker-card ${isMobile ? "always-show-add" : ""}`}
      draggable
      title={payload.label}
      {...interactive}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(payload.id));
        drag.start(payload);
      }}
      onDragEnd={drag.end}
    >
      <div className="thumbnail-wrapper">
        {thumb ? (
          <img src={thumb} alt="" className="card-thumbnail" />
        ) : (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name={fallbackIcon} size={20} style={{ opacity: 0.25 }} />
          </div>
        )}
        <span className="card-duration" style={{ fontSize: "0.65rem", padding: "1px 4px" }}>{duration}</span>
      </div>
      <div className="picker-card-content">
        <span className="picker-card-title">{title}</span>
        {meta && <div className="picker-card-meta">{meta}</div>}
      </div>
    </div>
  );
}
