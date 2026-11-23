"use client";

import React from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import { outputsFor, type DisplayChannel, type DisplayOutput } from "@/lib/displayChannel";

interface DisplayOutputSwitchProps {
  channel: DisplayChannel;
  displayOutput: DisplayOutput | null;
  onSetDisplayOutput: (output: DisplayOutput) => void;
  label?: string;
  hint?: string;
}

const OUTPUT_VIEW: Record<DisplayOutput, { icon: string; label: string; hint?: string }> = {
  kiosk: { icon: "tv", label: "dashboard.displayOutputKiosk" },
  cinema: { icon: "theaters", label: "dashboard.displayOutputCinema" },
  radio: { icon: "radio", label: "dashboard.displayOutputRadio", hint: "dashboard.displayOutputRadioHint" },
  signage: { icon: "slideshow", label: "dashboard.displayOutputSignage", hint: "dashboard.displayOutputSignageHint" },
};

export default function DisplayOutputSwitch({ channel, displayOutput, onSetDisplayOutput, label, hint }: DisplayOutputSwitchProps) {
  const { t } = useAppSettings();
  const active = displayOutput ?? "kiosk";
  return (
    <div className="display-output-switch" title={hint ?? t("dashboard.displayOutputHint")}>
      <span className="display-output-label">{label ?? t("dashboard.displayOutputLabel")}</span>
      <div className="display-output-buttons">
        {outputsFor(channel).map((output) => {
          const view = OUTPUT_VIEW[output];
          return (
            <button
              key={output}
              className={`display-output-btn olc-press ${active === output ? "active" : ""}`}
              onClick={() => onSetDisplayOutput(output)}
              disabled={displayOutput === null}
              title={view.hint ? t(view.hint) : undefined}
            >
              <Icon name={view.icon} size={16} />
              {t(view.label)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
