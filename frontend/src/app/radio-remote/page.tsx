"use client";

import React, { useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { RadioChannelId } from "@/lib/displayChannel";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import Icon from "@/components/Icon";

const STORAGE_KEY = "bobine.radioRemote.channel";

function readStoredChannel(): RadioChannelId {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "radio_cable" || stored === "radio_network") return stored;
  } catch {
  }
  return "radio_network";
}

function readRequestedChannel(): RadioChannelId | null {
  const requested = new URLSearchParams(window.location.search).get("channel");
  if (requested === "cable") return "radio_cable";
  if (requested === "network") return "radio_network";
  return null;
}

export default function RadioRemotePage() {
  const { t } = useAppSettings();
  const [channel, setChannel] = useState<RadioChannelId | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture unique d'une préférence locale après hydratation
    setChannel(readRequestedChannel() ?? readStoredChannel());
  }, []);

  const selectChannel = (next: RadioChannelId) => {
    setChannel(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
    }
  };

  return (
    <div className="dashboard-container">
      <div className="live-block channel-card radio-remote-head">
        <div className="channel-card-left">
          <h3>
            <Icon name="graphic_eq" size={18} />
            {t("radioRemote.title")}
          </h3>
          <span className="status-pill neutral">
            {channel === "radio_cable" ? t("radioRemote.outputCable") : t("radioRemote.outputNetwork")}
          </span>
        </div>
        <div className="channel-card-right">
          <a
            href={`/radio?channel=${channel === "radio_cable" ? "cable" : "network"}`}
            target="_blank"
            rel="noopener noreferrer"
            className="status-pill radio-remote-open"
            style={{ textDecoration: "none" }}
          >
            {t("radioRemote.openPlayer")}
          </a>
          <div className="display-output-switch" role="tablist" aria-label={t("radioRemote.outputTabs")}>
            <span className="display-output-label">{t("radioRemote.outputTabs")}</span>
            <div className="display-output-buttons">
              <button
                role="tab"
                aria-selected={channel === "radio_cable"}
                className={`display-output-btn olc-press ${channel === "radio_cable" ? "active" : ""}`}
                onClick={() => selectChannel("radio_cable")}
                title={t("radioRemote.outputCableTitle")}
              >
                <Icon name="cable" size={16} />
                {t("radioRemote.outputCable")}
              </button>
              <button
                role="tab"
                aria-selected={channel === "radio_network"}
                className={`display-output-btn olc-press ${channel === "radio_network" ? "active" : ""}`}
                onClick={() => selectChannel("radio_network")}
                title={t("radioRemote.outputNetworkTitle")}
              >
                <Icon name="wifi" size={16} />
                {t("radioRemote.outputNetwork")}
              </button>
            </div>
          </div>
        </div>
      </div>
      {channel && <RadioRemotePanel key={channel} channel={channel} />}
    </div>
  );
}
