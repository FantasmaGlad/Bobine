"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { TIMING_SETTING_KEYS } from "@/lib/settingsBounds";
import TimingField from "./timing/TimingField";
import { useTimingSettings } from "./timing/useTimingSettings";

export default function PlaybackTimingSettings() {
  const { t } = useAppSettings();
  const { saved, draft, status, commit, edit } = useTimingSettings();

  return (
    <section className="live-block" aria-labelledby="timing-title">
      <h3 id="timing-title">{t("settingsPage.timing.title")}</h3>
      <p className="settings-hint">{t("settingsPage.timing.intro")}</p>
      <div className="settings-timing-grid">
        {TIMING_SETTING_KEYS.map((key) => (
          <TimingField
            key={key}
            settingKey={key}
            shown={draft[key] ?? (saved[key] === undefined ? "" : String(saved[key]))}
            state={status[key] ?? "idle"}
            onEdit={(text) => edit(key, text)}
            onCommit={() => void commit(key)}
            t={t}
          />
        ))}
      </div>
    </section>
  );
}
