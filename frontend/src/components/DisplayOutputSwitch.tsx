"use client";

import React from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import type { DisplayOutput } from "@/lib/displayChannel";

interface DisplayOutputSwitchProps {
  displayOutput: DisplayOutput | null;
  onSetDisplayOutput: (output: DisplayOutput) => void;
  label?: string;
  hint?: string;
  allowRadio?: boolean;
}

export default function DisplayOutputSwitch({
  displayOutput,
  onSetDisplayOutput,
  label,
  hint,
  allowRadio = false,
}: DisplayOutputSwitchProps) {
  const { t } = useAppSettings();
  return (
    <div className="display-output-switch" title={hint ?? t("dashboard.displayOutputHint")}>
      <span className="display-output-label">{label ?? t("dashboard.displayOutputLabel")}</span>
      <div className="display-output-buttons">
        <button
          className={`display-output-btn olc-press ${displayOutput === "kiosk" || displayOutput === null ? "active" : ""}`}
          onClick={() => onSetDisplayOutput("kiosk")}
          disabled={displayOutput === null}
        >
          <Icon name="tv" size={16} />
          {t("dashboard.displayOutputKiosk")}
        </button>
        <button
          className={`display-output-btn olc-press ${displayOutput === "cinema" ? "active" : ""}`}
          onClick={() => onSetDisplayOutput("cinema")}
          disabled={displayOutput === null}
        >
          <Icon name="theaters" size={16} />
          {t("dashboard.displayOutputCinema")}
        </button>
        {allowRadio && (
          <button
            className={`display-output-btn olc-press ${displayOutput === "radio" ? "active" : ""}`}
            onClick={() => onSetDisplayOutput("radio")}
            disabled={displayOutput === null}
            title={t("dashboard.displayOutputRadioHint")}
          >
            <Icon name="radio" size={16} />
            {t("dashboard.displayOutputRadio")}
          </button>
        )}
      </div>
    </div>
  );
}
