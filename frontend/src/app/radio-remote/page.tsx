"use client";

import { useClientSnapshot } from "@/lib/useClientSnapshot";
import React, { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { buildOutputUrl } from "@/lib/displayChannel";
import { DEFAULT_RADIO_CHANNEL, OUTPUTS, isOutputId, isRadioChannel, outputById, outputOfRadio, type RadioChannelId } from "@/lib/outputs";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import Icon from "@/components/Icon";

const STORAGE_KEY = "bobine.radioRemote.channel";

function readStoredChannel(): RadioChannelId {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isRadioChannel(stored)) return stored;
  } catch {
  }
  return DEFAULT_RADIO_CHANNEL;
}

function readRequestedChannel(): RadioChannelId | null {
  const requested = new URLSearchParams(window.location.search).get("channel");
  return isOutputId(requested) ? outputById(requested).radioChannel : null;
}

export default function RadioRemotePage() {
  const { t } = useAppSettings();
  const stored = useClientSnapshot<RadioChannelId | null>(() => readRequestedChannel() ?? readStoredChannel(), null);
  const [chosen, setChannel] = useState<RadioChannelId | null>(null);
  const channel = chosen ?? stored;

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
            {channel && t(`outputs.${channel}`)}
          </span>
        </div>
        <div className="channel-card-right">
          <a
            href={buildOutputUrl("radio", "", outputOfRadio(channel ?? DEFAULT_RADIO_CHANNEL).id)}
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
              {OUTPUTS.map((output) => (
                <button
                  key={output.radioChannel}
                  role="tab"
                  aria-selected={channel === output.radioChannel}
                  className={`display-output-btn olc-press ${channel === output.radioChannel ? "active" : ""}`}
                  onClick={() => selectChannel(output.radioChannel)}
                  title={t("radioRemote.outputTitle", { output: t(`outputs.${output.id}`), path: buildOutputUrl("radio", "", output.id) })}
                >
                  <Icon name={output.wired ? "cable" : "wifi"} size={16} />
                  {t(`outputs.${output.radioChannel}`)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      {channel && <RadioRemotePanel key={channel} channel={channel} />}
    </div>
  );
}
