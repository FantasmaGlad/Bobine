"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { devicesRequest, type DevicesStatus } from "@/lib/devicesApi";
import { initialSetFlow, submitSetCode, type SetFlow } from "@/lib/pinEntry";
import PinEntry, { type PinStatus } from "./PinEntry";
import { errorText, type SectionProps } from "./common";

interface GateProps {
  status: DevicesStatus;
  onChanged: () => void;
  notify: SectionProps["notify"];
  t: SectionProps["t"];
}

function pinLabels(t: SectionProps["t"]) {
  return {
    group: t("devices.pin.group"),
    delete: t("devices.pin.delete"),
    filled: (count: number, total: number) => t("devices.pin.filled", { count, total }),
  };
}

/** Écran affiché tant que l'accès n'est pas accordé : fonction désactivée, PIN à définir ou à saisir. */
export function AccessGate({ status, onChanged, notify, t }: GateProps) {
  const [pinStatus, setPinStatus] = useState<PinStatus>("idle");
  const [resetKey, setResetKey] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [lockedFor, setLockedFor] = useState(status.retry_after ?? 0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reprend le blocage annoncé par le serveur
    setLockedFor(status.retry_after ?? 0);
  }, [status.retry_after]);
  useEffect(() => {
    if (lockedFor <= 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- fin du blocage : les bulles se réactivent
      setPinStatus((s) => (s === "locked" ? "idle" : s));
      return;
    }
    setPinStatus("locked");
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

  const login = async (pin: string) => {
    const result = await devicesRequest("/session", { body: { pin } });
    if (result.ok) {
      setMessage(null);
      setPinStatus("success");
      setTimeout(onChanged, 520); // laisse l'animation de succès se terminer
      return;
    }
    const retry = Number(result.error.extra.retry_after ?? 0);
    if (retry > 0) {
      setLockedFor(retry);
      setMessage(null);
      return;
    }
    const left = result.error.extra.attempts_left;
    setMessage(typeof left === "number" && result.error.code === "bad_pin" ? t("devices.access.badPinLeft", { count: left }) : errorText(result.error, t));
    setPinStatus("error");
    setTimeout(() => {
      setPinStatus("idle");
      setResetKey((k) => k + 1);
    }, 520);
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

  const caption =
    lockedFor > 0 ? t("devices.access.locked", { seconds: lockedFor }) : message ?? t("devices.pin.enter");
  return (
    <div className="live-block dv-gate dv-gate--pin">
      <PinEntry
        length={status.pin_length}
        status={pinStatus}
        caption={caption}
        resetKey={resetKey}
        disabled={lockedFor > 0}
        onComplete={login}
        labels={pinLabels(t)}
      />
    </div>
  );
}

/** Sécurité de la fonction — uniquement depuis l'écran local (présence physique). */
export function SecurityPanel({ status, onChanged, notify, t }: GateProps) {
  const [flow, setFlow] = useState<SetFlow>(initialSetFlow);
  const [pinStatus, setPinStatus] = useState<PinStatus>("idle");
  const [resetKey, setResetKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [confirmDisable, setConfirmDisable] = useState(false);

  const call = async (path: string, init: { method?: string; body?: unknown }, okMessage: string) => {
    setBusy(true);
    const result = await devicesRequest(path, init);
    setBusy(false);
    if (result.ok) {
      notify(okMessage, "success");
      onChanged();
      return true;
    }
    notify(errorText(result.error, t), "error");
    return false;
  };

  const onComplete = async (code: string) => {
    const result = submitSetCode(flow, code);
    if (result.kind === "next") {
      setFlow(result.flow);
      setResetKey((k) => k + 1);
    } else if (result.kind === "mismatch") {
      setPinStatus("error");
      setTimeout(() => {
        setFlow(result.flow);
        setPinStatus("idle");
        setResetKey((k) => k + 1);
      }, 520);
    } else {
      setPinStatus("success");
      const saved = await call("/admin/pin", { body: { pin: result.pin } }, t("devices.security.pinSaved"));
      setTimeout(() => {
        setFlow(initialSetFlow);
        setPinStatus("idle");
        setResetKey((k) => k + 1);
      }, saved ? 700 : 100);
    }
  };

  const caption =
    flow.mismatch ? t("devices.pin.mismatch") : flow.phase === "new" ? t("devices.pin.new") : t("devices.pin.confirm");

  return (
    <div className="dv-section">
      <div className="live-block dv-gate dv-gate--pin">
        <div key={flow.phase} className="pin-slide">
          <PinEntry
            length={status.pin_length}
            status={pinStatus}
            caption={caption}
            resetKey={resetKey}
            disabled={busy}
            onComplete={onComplete}
            labels={pinLabels(t)}
          />
        </div>
        {status.pin_set && (
          <button type="button" className="dv-link-btn" disabled={busy} onClick={() => call("/admin/pin", { method: "DELETE" }, t("devices.security.pinCleared"))}>
            <Icon name="lock_open" size={14} /> {t("devices.security.clearPin")}
          </button>
        )}
      </div>
      <div className="dv-quiet-actions">
        {confirmDisable ? (
          <button type="button" className="dv-link-btn dv-link-btn--danger" disabled={busy} onClick={() => call("/admin/enable", { body: { enabled: false } }, t("devices.security.disabled"))}>
            <Icon name="power_settings_new" size={14} /> {t("devices.security.disable")}
          </button>
        ) : (
          <button type="button" className="dv-link-btn" onClick={() => setConfirmDisable(true)}>
            <Icon name="power_settings_new" size={14} /> {t("devices.security.featureTitle")}
          </button>
        )}
      </div>
    </div>
  );
}
