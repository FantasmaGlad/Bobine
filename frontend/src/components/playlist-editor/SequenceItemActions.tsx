"use client";

import React from "react";
import Icon from "@/components/Icon";

const ROUND = { width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" } as const;

export default function SequenceItemActions({ index, count, style, labels, onMoveUp, onMoveDown, onRemove }: {
  index: number;
  count: number;
  style: React.CSSProperties;
  labels: { up: string; down: string; remove: string };
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <div style={style}>
      <button type="button" className="btn btn-secondary" style={ROUND} onClick={() => onMoveUp(index)} disabled={index === 0} title={labels.up}>
        <Icon name="arrow_upward" size={14} />
      </button>
      <button type="button" className="btn btn-secondary" style={ROUND} onClick={() => onMoveDown(index)} disabled={index === count - 1} title={labels.down}>
        <Icon name="arrow_downward" size={14} />
      </button>
      <button type="button" className="btn btn-danger" style={ROUND} onClick={() => onRemove(index)} title={labels.remove}>
        <Icon name="close" size={14} />
      </button>
    </div>
  );
}
