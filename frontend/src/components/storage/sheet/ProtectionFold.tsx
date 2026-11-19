"use client";

import Icon from "@/components/Icon";
import { longevitySummary, STANDBY_CHOICES } from "@/lib/storage/display";
import { type LongevityItem, type LongevitySettings, type StorageVolume } from "@/lib/storage/types";
import { tr, type StorageCtx } from "../common";

const TOGGLES: Array<{ id: LongevityItem["id"]; setting: keyof LongevitySettings }> = [
  { id: "read_only", setting: "read_only" },
  { id: "noatime", setting: "noatime" },
  { id: "noexec", setting: "noexec" },
  { id: "smart", setting: "smart_monitor" },
];

function itemStatusIcon(status: LongevityItem["status"]): string {
  return status === "applied" ? "check_circle" : status === "unavailable" ? "block" : status === "disabled" ? "toggle_off" : "schedule";
}

function ProtectionRow({ t, item, settings, disabled, setSetting }: {
  t: StorageCtx["t"]; item: LongevityItem; settings: LongevitySettings | undefined; disabled: boolean; setSetting: (values: Partial<LongevitySettings>) => void;
}) {
  const toggle = TOGGLES.find((x) => x.id === item.id);
  const reason = item.reason ? tr(t, `storage.protection.reasons.${item.reason}`) : "";
  const label = item.id === "standby" && settings?.standby_minutes
    ? `${t("storage.protection.items.standby")} · ${t("storage.protection.standbyMinutes", { count: settings.standby_minutes })}` : t(`storage.protection.items.${item.id}`);
  return (
    <div className="dv-row">
      <span className="dv-icon"><Icon name={itemStatusIcon(item.status)} size={20} /></span>
      <span className="dv-text">
        <span className="dv-title">{label}</span>
        <span className="dv-sub">
          {t(`storage.protection.status.${item.status}`)}{reason ? ` · ${reason}` : ""}
        </span>
      </span>
      {toggle && settings && (
        <label className="st-switch">
          <input
            type="checkbox"
            aria-label={t(`storage.protection.items.${item.id}`)}
            checked={!!settings[toggle.setting]}
            disabled={disabled}
            onChange={(e) => setSetting({ [toggle.setting]: e.target.checked })}
          />
        </label>
      )}
      {item.id === "standby" && settings && item.reason !== "not_rotational" && (
        <select
          className="form-control st-select"
          aria-label={t("storage.protection.standbyChoice")}
          value={settings.standby_minutes}
          disabled={disabled}
          onChange={(e) => setSetting({ standby_minutes: Number(e.target.value) })}
        >
          {STANDBY_CHOICES.map((m) => <option key={m} value={m}>{m === 0 ? t("storage.protection.standbyOff") : t("storage.protection.standbyMinutes", { count: m })}</option>)}
        </select>
      )}
    </div>
  );
}

export default function ProtectionFold({ t, volume, disabled, setSetting }: {
  t: StorageCtx["t"]; volume: StorageVolume; disabled: boolean; setSetting: (values: Partial<LongevitySettings>) => void;
}) {
  const summary = longevitySummary(volume.longevity);
  const settings = volume.library?.settings;
  return (
    <details className="st-fold">
      <summary>
        <Icon name="shield" size={20} />
        <span className="st-fold-title">{t("storage.details.protection")}</span>
        <span className="dv-sub">
          {!summary.recommended ? t("storage.details.protectionCustom")
            : summary.unavailable > 0 ? t("storage.details.protectionPartial", { count: summary.unavailable }) : t("storage.details.protectionOk")}
        </span>
      </summary>
      <div className="dv-list">
        {volume.longevity.map((item) => (
          <ProtectionRow key={item.id} t={t} item={item} settings={settings} disabled={disabled} setSetting={setSetting} />
        ))}
      </div>
    </details>
  );
}
