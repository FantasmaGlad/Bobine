"use client";

import { useClientChoice, useClientSnapshot } from "@/lib/useClientSnapshot";
import { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { copyText } from "@/lib/clipboard";
import { VideoProfilePreference, getVideoProfilePreference, setVideoProfilePreference } from "@/lib/clientCodecSupport";
import { compatReport, readCapabilities, type Capabilities } from "./browser-compat/capabilities";
import { CompatActions, CompatTips, ProfileChooser } from "./browser-compat/CompatControls";
import CompatLists from "./browser-compat/CompatLists";
import { runPlaybackProbe } from "./browser-compat/playbackProbe";
import { useAutoWebRendition } from "./browser-compat/useAutoWebRendition";

export default function BrowserCompatibility() {
  const { t } = useAppSettings();
  const caps = useClientSnapshot<Capabilities | null>(readCapabilities, null);
  const [preference, setPreference] = useClientChoice<VideoProfilePreference>(getVideoProfilePreference, "auto");
  const { autoGenerate, toggleAutoGenerate } = useAutoWebRendition();
  const [testState, setTestState] = useState<{ running: boolean; text: string | null }>({ running: false, text: null });
  const [copied, setCopied] = useState(false);

  const changePreference = (value: VideoProfilePreference) => {
    setVideoProfilePreference(value);
    setPreference(value);
  };
  const runPlaybackTest = async () => {
    setTestState({ running: true, text: null });
    setTestState({ running: false, text: await runPlaybackProbe(t) });
  };
  const copyReport = async () => {
    if (!caps) return;
    await copyText(compatReport(caps, testState.text));
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  if (!caps) return null;
  return (
    <section className="live-block" id="browser-compat-section">
      <h3>
        <Icon name="travel_explore" size={18} /> {t("browserCompat.section")}
      </h3>
      <p className="settings-hint" style={{ marginTop: 0 }}>{t("browserCompat.hint")}</p>
      <CompatLists caps={caps} t={t} />
      <ProfileChooser preference={preference} onChange={changePreference} t={t} />
      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
        <input type="checkbox" checked={autoGenerate} onChange={(e) => toggleAutoGenerate(e.target.checked)} />
        {t("browserCompat.autoGenerate")}
      </label>
      <p className="settings-hint">{t("browserCompat.autoGenerateHint")}</p>
      <CompatActions running={testState.running} text={testState.text} copied={copied} onTest={runPlaybackTest} onCopy={copyReport} t={t} />
      <CompatTips t={t} />
    </section>
  );
}
