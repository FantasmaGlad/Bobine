"use client";

import React, { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { SendRadioCommand } from "./types";

const PRESETS = [25, 50, 75, 100];

export default function VolumeControl({ volume, sendCommand }: { volume: number; sendCommand: SendRadioCommand }) {
  const { t } = useAppSettings();
  const [dragValue, setDragValue] = useState<number | null>(null);
  const displayVolume = dragValue ?? volume;
  return (
    <div className="volume-row">
      <span>{t("radioRemote.volume")}</span>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={displayVolume}
        onChange={(e) => {
          const value = Number(e.target.value);
          setDragValue(value);
          sendCommand("volume", { volume: value });
        }}
        onMouseUp={() => setDragValue(null)}
        className="volume-slider"
      />
      <span className="volume-value">{displayVolume}%</span>
      <div className="volume-presets">
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            className={`volume-preset-btn ${displayVolume === preset ? "active" : ""}`}
            onClick={() => {
              setDragValue(preset);
              sendCommand("volume", { volume: preset });
              setTimeout(() => setDragValue(null), 100);
            }}
          >
            {preset}%
          </button>
        ))}
      </div>
    </div>
  );
}
