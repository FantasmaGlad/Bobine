"use client";

import Icon from "@/components/Icon";
import { formatBytes, healthWarningKeys, overallTone } from "@/lib/storage/display";
import { type Health, type StorageVolume } from "@/lib/storage/types";
import { tr, type StorageCtx } from "../common";

export default function HealthBlock({ t, lang, volume, shownHealth, busy, refreshHealth }: {
  t: StorageCtx["t"]; lang: StorageCtx["lang"]; volume: StorageVolume; shownHealth: Health | null; busy: boolean; refreshHealth: () => void;
}) {
  const library = volume.library;
  const tone = overallTone({ health: shownHealth, library });
  const warnings = healthWarningKeys(shownHealth);
  const healthTitle = tone === "critical" ? t("storage.details.healthCritical") : tone === "warning" ? t("storage.details.healthWarning")
    : shownHealth?.available ? t("storage.details.healthOk") : t("storage.details.healthUnknown");
  return (
    <div className="dv-detail-block">
      <div className="dv-row">
        <span className="dv-icon"><Icon name={tone === "critical" || tone === "warning" ? "warning" : "monitor_heart"} size={22} /></span>
        <span className="dv-text">
          <span className="dv-title">{healthTitle}</span>
          <span className="dv-sub">
            {shownHealth?.available
              ? [
                  shownHealth.temperature_c != null ? t("storage.details.temperature", { value: shownHealth.temperature_c }) : "",
                  shownHealth.power_on_hours != null ? t("storage.details.hours", { value: shownHealth.power_on_hours }) : "",
                  shownHealth.wear_percent_used != null ? t("storage.details.wear", { value: Math.round(shownHealth.wear_percent_used) }) : "",
                ].filter(Boolean).join(" · ")
              : tr(t, `storage.healthReasons.${shownHealth?.reason ?? "no_smart"}`)}
          </span>
          {warnings.map((w) => <span key={w} className="dv-sub">{tr(t, `storage.warnings.${w}`, w)}</span>)}
          {(library?.bytes_written ?? 0) > 0 && <span className="dv-sub">{t("storage.details.written", { size: formatBytes(library?.bytes_written, lang) })}</span>}
          {library?.wear_level === "warning" && <span className="dv-sub">{t("storage.details.wearWarning")}</span>}
          {library?.wear_level === "critical" && <span className="dv-error">{t("storage.details.wearCritical")}</span>}
        </span>
        <span className="dv-actions"><button type="button" className="btn btn-secondary" disabled={busy} onClick={refreshHealth}><Icon name="refresh" size={16} /> {t("storage.details.refresh")}</button></span>
      </div>
    </div>
  );
}
