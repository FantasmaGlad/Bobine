"use client";

import React, { useState } from "react";
import { formatTime } from "@/lib/format";
import type { SendRadioCommand } from "./types";

export default function SeekBar({ position, duration, sendCommand }: { position: number; duration: number; sendCommand: SendRadioCommand }) {
  const [dragValue, setDragValue] = useState<number | null>(null);
  const displayPosition = dragValue ?? position;
  return (
    <div className="live-progress">
      <span className="live-time">{formatTime(displayPosition)}</span>
      <input
        type="range"
        min={0}
        max={duration || 0}
        step={1}
        value={displayPosition}
        onChange={(e) => setDragValue(Number(e.target.value))}
        onMouseUp={(e) => {
          const value = Number((e.target as HTMLInputElement).value);
          sendCommand("radio_seek", { position_seconds: value });
          setDragValue(null);
        }}
        className="seek-slider"
      />
      <span className="live-time">{formatTime(duration)}</span>
    </div>
  );
}
