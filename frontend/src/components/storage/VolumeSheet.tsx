"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import {
  encodeKey, formatBytes, fsLabel, healthWarningKeys, longevitySummary, overallTone, STANDBY_CHOICES, storageRequest, visibleNotes,
  type Health, type LongevityItem, type LongevitySettings, type StorageVolume,
} from "@/lib/storageApi";
import { storageErrorText, tr, type StorageCtx } from "./common";

interface Props extends StorageCtx {
  volume: StorageVolume | null;
  onClose: () => void;
  onChanged: () => void;
  onAdvice: () => void;
}

const TOGGLES: Array<{ id: LongevityItem["id"]; setting: keyof LongevitySettings }> = [
  { id: "read_only", setting: "read_only" },
  { id: "noatime", setting: "noatime" },
  { id: "noexec", setting: "noexec" },
  { id: "smart", setting: "smart_monitor" },
];

function itemStatusIcon(status: LongevityItem["status"]): string {
  return status === "applied" ? "check_circle" : status === "unavailable" ? "block" : status === "disabled" ? "toggle_off" : "schedule";
}

/** Options d'un support : santé, protection (repliée, valeurs recommandées déjà appliquées), format, retrait sûr. */
export default function VolumeSheet({ volume, onClose, onChanged, onAdvice, t, lang, notify }: Props) {
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);
  if (!volume) return <Sheet open={false} onClose={onClose}>{null}</Sheet>;

  const key = encodeKey(volume.key);
  const library = volume.library;
  const registered = !!library?.registered;
  const settings = library?.settings;
  const summary = longevitySummary(volume.longevity);
  const shownHealth = health ?? volume.health;
  const tone = overallTone({ health: shownHealth, library });
  const warnings = healthWarningKeys(shownHealth);

  const run = async (action: () => Promise<{ ok: boolean; error?: Parameters<typeof storageErrorText>[0] }>, ok?: string) => {
    setBusy(true);
    const result = await action();
    setBusy(false);
    if (result.ok) {
      if (ok) notify(ok, "success");
      onChanged();
    } else if (result.error) notify(storageErrorText(result.error, t, lang), "error");
  };

  const setSetting = (values: Partial<LongevitySettings>) =>
    run(async () => storageRequest(`/volumes/${key}/settings`, { method: "PUT", body: values }));
  const eject = () =>
    run(async () => {
      const result = await storageRequest(`/volumes/${key}/eject`, { body: {} });
      if (result.ok) {
        notify(t("storage.ejected", { name: volume.name }), "success");
        onClose();
      }
      return result;
    });
  const stopExtension = () =>
    run(async () => {
      const result = await storageRequest(`/volumes/${key}/library?purge=true`, { method: "DELETE" });
      if (result.ok) {
        setConfirmStop(false);
        notify(t("storage.extension.stopped"), "success");
      }
      return result;
    });
  const refreshHealth = async () => {
    setBusy(true);
    const result = await storageRequest<Health>(`/volumes/${key}/health?refresh=true`);
    setBusy(false);
    if (result.ok) setHealth(result.data);
    else notify(storageErrorText(result.error, t, lang), "error");
  };

  const videos = library?.stats?.videos ?? 0;
  const tracks = (library?.stats?.audio_tracks ?? 0) + (library?.stats?.radio_tracks ?? 0);
  const libraryCount = [videos ? t("storage.extension.videos", { count: videos }) : "", tracks ? t("storage.extension.tracks", { count: tracks }) : ""].filter(Boolean).join(" · ") || t("storage.extension.empty");
  const total = (library?.stats?.videos ?? 0) + (library?.stats?.audio_tracks ?? 0) + (library?.stats?.radio_tracks ?? 0);
  const healthTitle = tone === "critical" ? t("storage.details.healthCritical") : tone === "warning" ? t("storage.details.healthWarning")
    : shownHealth?.available ? t("storage.details.healthOk") : t("storage.details.healthUnknown");
  const itemReason = (item: LongevityItem) => (item.reason ? tr(t, `storage.protection.reasons.${item.reason}`) : "");
  const itemLabel = (item: LongevityItem) =>
    item.id === "standby" && settings?.standby_minutes ? `${t("storage.protection.items.standby")} · ${t("storage.protection.standbyMinutes", { count: settings.standby_minutes })}` : t(`storage.protection.items.${item.id}`);

  return (
    <Sheet
      open
      onClose={onClose}
      title={volume.name}
      closeLabel={t("storage.close")}
      footer={
        volume.connected ? (
          <div className="dv-actions">
            <button type="button" className="btn btn-primary" disabled={busy || volume.state === "busy"} onClick={eject}><Icon name="eject" size={18} /> {t("storage.eject")}</button>
          </div>
        ) : undefined
      }
    >
      <div className="dv-detail">
        <div className="dv-detail-block">
          <div className="dv-row">
            <span className="dv-icon"><Icon name={verdictIcon(volume.assessment.verdict)} size={22} /></span>
            <span className="dv-text">
              <span className="dv-title">{t(`storage.verdict.${volume.assessment.verdict}`)} · {fsLabel(volume.fstype)}</span>
              <span className="dv-sub">{tr(t, `storage.fsReasons.${volume.assessment.reason}`)}</span>
              {visibleNotes(volume.assessment).length > 0 && (
                <span className="dv-sub">{visibleNotes(volume.assessment).map((n) => tr(t, `storage.fsNotes.${n}`)).filter(Boolean).join(" · ")}</span>
              )}
            </span>
            <span className="dv-actions"><button type="button" className="btn btn-secondary" onClick={onAdvice}><Icon name="help" size={16} /> {t("storage.details.formatAdvice")}</button></span>
          </div>
        </div>

        {volume.connected && (
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
        )}

        {volume.connected && (
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
              {volume.longevity.map((item) => {
                const toggle = TOGGLES.find((x) => x.id === item.id);
                return (
                  <div key={item.id} className="dv-row">
                    <span className="dv-icon"><Icon name={itemStatusIcon(item.status)} size={20} /></span>
                    <span className="dv-text">
                      <span className="dv-title">{itemLabel(item)}</span>
                      <span className="dv-sub">
                        {t(`storage.protection.status.${item.status}`)}{itemReason(item) ? ` · ${itemReason(item)}` : ""}
                      </span>
                    </span>
                    {toggle && settings && (
                      <label className="st-switch">
                        <input
                          type="checkbox"
                          aria-label={t(`storage.protection.items.${item.id}`)}
                          checked={!!settings[toggle.setting]}
                          disabled={busy || !registered}
                          onChange={(e) => setSetting({ [toggle.setting]: e.target.checked })}
                        />
                      </label>
                    )}
                    {item.id === "standby" && settings && item.reason !== "not_rotational" && (
                      <select
                        className="form-control st-select"
                        aria-label={t("storage.protection.standbyChoice")}
                        value={settings.standby_minutes}
                        disabled={busy || !registered}
                        onChange={(e) => setSetting({ standby_minutes: Number(e.target.value) })}
                      >
                        {STANDBY_CHOICES.map((m) => <option key={m} value={m}>{m === 0 ? t("storage.protection.standbyOff") : t("storage.protection.standbyMinutes", { count: m })}</option>)}
                      </select>
                    )}
                  </div>
                );
              })}
            </div>
          </details>
        )}

        {registered && (
          <div className="dv-detail-block">
            <div className="dv-row">
              <span className="dv-icon"><Icon name="hard_drive" size={22} /></span>
              <span className="dv-text">
                <span className="dv-title">{libraryCount}</span>
              </span>
              <span className="dv-actions">
                {confirmStop ? (
                  <button type="button" className="btn btn-danger" disabled={busy} onClick={stopExtension}>{t("storage.extension.stopConfirm", { count: total })}</button>
                ) : (
                  <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => (total > 0 ? setConfirmStop(true) : void stopExtension())}>{t("storage.extension.stop")}</button>
                )}
              </span>
            </div>
          </div>
        )}
      </div>
    </Sheet>
  );
}

function verdictIcon(verdict: string): string {
  return verdict === "recommended" ? "verified" : verdict === "acceptable" ? "check_circle" : verdict === "discouraged" ? "warning" : "help";
}
