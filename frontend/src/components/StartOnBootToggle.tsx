"use client";

import { useClientChoice, useClientSnapshot } from "@/lib/useClientSnapshot";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getNativeBridge } from "@/lib/nativeBridge";

export default function StartOnBootToggle() {
  const { t } = useAppSettings();
  const available = useClientSnapshot(() => getNativeBridge() !== null, false);
  const [enabled, setEnabled] = useClientChoice<boolean>(() => getNativeBridge()?.getStartOnBoot() ?? null, false);

  if (!available) return null;

  return (
    <section className="live-block" id="section-boot">
      <h3 style={{ margin: "0 0 6px 0" }}>
        <Icon name="power_settings_new" size={18} /> {t("settingsPage.startOnBoot.title")}
      </h3>
      <p className="settings-hint" style={{ margin: "0 0 12px 0" }}>
        {t("settingsPage.startOnBoot.hint")}
      </p>
      <label className="settings-toggle-row">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => {
            setEnabled(event.target.checked);
            getNativeBridge()?.setStartOnBoot(event.target.checked);
          }}
        />
        <span>{t("settingsPage.startOnBoot.label")}</span>
      </label>
    </section>
  );
}
