"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { devicesRequest, isValidPin, sanitizePin, type DevicesStatus } from "@/lib/devicesApi";
import { errorText, type SectionProps } from "./common";

interface GateProps {
  status: DevicesStatus;
  onChanged: () => void;
  notify: SectionProps["notify"];
  t: SectionProps["t"];
}

/** Écran affiché tant que l'accès n'est pas accordé : fonction désactivée, PIN à définir ou à saisir. */
export function AccessGate({ status, onChanged, notify, t }: GateProps) {
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [lockedFor, setLockedFor] = useState(status.retry_after ?? 0);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reprend le blocage annoncé par le serveur
    setLockedFor(status.retry_after ?? 0);
  }, [status.retry_after]);
  useEffect(() => {
    if (lockedFor <= 0) return;
    const timer = setInterval(() => setLockedFor((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [lockedFor]);

  const enable = async () => {
    setBusy(true);
    const result = await devicesRequest("/admin/enable", { body: { enabled: true } });
    setBusy(false);
    if (result.ok) onChanged();
    else notify(errorText(result.error, t), "error");
  };

  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidPin(pin, status.pin_length)) return;
    setBusy(true);
    const result = await devicesRequest("/session", { body: { pin } });
    setBusy(false);
    setPin("");
    if (result.ok) {
      setMessage(null);
      onChanged();
      return;
    }
    const retry = Number(result.error.extra.retry_after ?? 0);
    if (retry > 0) setLockedFor(retry);
    const left = result.error.extra.attempts_left;
    setMessage(
      typeof left === "number" && result.error.code === "bad_pin"
        ? t("devices.access.badPinLeft", { count: left })
        : errorText(result.error, t),
    );
  };

  if (status.access === "disabled") {
    return (
      <div className="live-block dv-gate">
        <Icon name="devices" size={40} style={{ opacity: 0.35 }} />
        <h3>{t("devices.access.disabledTitle")}</h3>
        <p className="settings-hint">{t("devices.access.disabledBody")}</p>
        {status.local ? (
          <button type="button" className="btn btn-primary" disabled={busy} onClick={enable}>
            <Icon name="power_settings_new" size={16} /> {t("devices.access.enable")}
          </button>
        ) : (
          <p className="settings-hint"><Icon name="lock" size={14} /> {t("devices.access.enableLocalOnly")}</p>
        )}
      </div>
    );
  }

  if (status.access === "pin_not_set") {
    return (
      <div className="live-block dv-gate">
        <Icon name="lock" size={40} style={{ opacity: 0.35 }} />
        <h3>{t("devices.access.pinNotSetTitle")}</h3>
        <p className="settings-hint">{t("devices.access.pinNotSetBody")}</p>
      </div>
    );
  }

  return (
    <form className="live-block dv-gate" onSubmit={login}>
      <Icon name="pin" size={40} style={{ opacity: 0.35 }} />
      <h3>{t("devices.access.pinTitle")}</h3>
      <p className="settings-hint">{t("devices.access.pinBody", { minutes: status.session_minutes })}</p>
      <input
        type="password"
        inputMode="numeric"
        autoComplete="off"
        autoFocus
        className="form-control dv-pin-input"
        placeholder={"•".repeat(status.pin_length)}
        value={pin}
        disabled={lockedFor > 0}
        onChange={(e) => setPin(sanitizePin(e.target.value, status.pin_length))}
        aria-label={t("devices.access.pinTitle")}
      />
      {lockedFor > 0 && <p className="dv-error">{t("devices.access.locked", { seconds: lockedFor })}</p>}
      {message && lockedFor === 0 && <p className="dv-error">{message}</p>}
      <button type="submit" className="btn btn-primary" disabled={busy || lockedFor > 0 || !isValidPin(pin, status.pin_length)}>
        <Icon name="login" size={16} /> {t("devices.access.unlock")}
      </button>
      <p className="settings-hint">{t("devices.access.httpWarning")}</p>
    </form>
  );
}

/** Sécurité de la fonction — uniquement depuis l'écran local (présence physique). */
export function SecurityPanel({ status, onChanged, notify, t }: GateProps) {
  const [pin, setPin] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const valid = isValidPin(pin, status.pin_length) && pin === again;

  const call = async (path: string, init: { method?: string; body?: unknown }, okMessage: string) => {
    setBusy(true);
    const result = await devicesRequest(path, init);
    setBusy(false);
    if (result.ok) {
      notify(okMessage, "success");
      setPin("");
      setAgain("");
      onChanged();
    } else {
      notify(errorText(result.error, t), "error");
    }
  };

  return (
    <div className="dv-section">
      <div className="live-block" style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "560px" }}>
        <h3 style={{ margin: 0 }}><Icon name="pin" size={18} /> {status.pin_set ? t("devices.security.changePin") : t("devices.security.setPin")}</h3>
        <p className="settings-hint" style={{ margin: 0 }}>{t("devices.security.pinHint", { length: status.pin_length })}</p>
        <input type="password" inputMode="numeric" autoComplete="off" className="form-control dv-pin-input" placeholder={t("devices.security.newPin")}
          value={pin} onChange={(e) => setPin(sanitizePin(e.target.value, status.pin_length))} />
        <input type="password" inputMode="numeric" autoComplete="off" className="form-control dv-pin-input" placeholder={t("devices.security.repeatPin")}
          value={again} onChange={(e) => setAgain(sanitizePin(e.target.value, status.pin_length))} />
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button type="button" className="btn btn-primary" disabled={busy || !valid} onClick={() => call("/admin/pin", { body: { pin } }, t("devices.security.pinSaved"))}>
            <Icon name="save" size={16} /> {t("devices.security.save")}
          </button>
          {status.pin_set && (
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => call("/admin/pin", { method: "DELETE" }, t("devices.security.pinCleared"))}>
              <Icon name="lock_open" size={16} /> {t("devices.security.clearPin")}
            </button>
          )}
        </div>
        <p className="settings-hint" style={{ margin: 0 }}>{t("devices.security.limits")}</p>
      </div>
      <div className="live-block" style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "560px" }}>
        <h3 style={{ margin: 0 }}><Icon name="power_settings_new" size={18} /> {t("devices.security.featureTitle")}</h3>
        <p className="settings-hint" style={{ margin: 0 }}>{t("devices.security.featureHint")}</p>
        <div><button type="button" className="btn btn-danger" disabled={busy} onClick={() => call("/admin/enable", { body: { enabled: false } }, t("devices.security.disabled"))}>
          {t("devices.security.disable")}
        </button></div>
      </div>
    </div>
  );
}
