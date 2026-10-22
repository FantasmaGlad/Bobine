"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { claimPairingCode, generatePairingCode, getPairingStatus, verifyPairingCode } from "@/lib/devicesApi";
import { useAppSettings } from "@/lib/AppSettingsContext";
import PinEntry, { type PinStatus } from "./PinEntry";
import PinSetupFlow from "./PinSetupFlow";
import { pinLabels } from "./pinLabels";
import { errorText, type SectionProps } from "./common";

/** Secondes → « m:ss ». */
function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  return `${m}:${String(seconds % 60).padStart(2, "0")}`;
}

interface ActiveCode {
  value: string;
  expiresAt: number;
}

/**
 * Écran local : le code d'association n'est émis que sur demande (bouton), puis affiché dans une pastille en
 * haut à droite jusqu'à son expiration. Un autre appareil du réseau ne peut pas en demander un (route locale).
 */
export function PairingCodeDisplay({ t }: { t: SectionProps["t"] }) {
  const { network } = useAppSettings();
  const [code, setCode] = useState<ActiveCode | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  // Reprend un code déjà émis (rechargement de la page) sans en créer un nouveau.
  useEffect(() => {
    let alive = true;
    void getPairingStatus().then((status) => {
      if (alive && status.ok && status.data.code) {
        setCode({ value: status.data.code, expiresAt: Date.now() + status.data.seconds_left * 1000 });
      }
    });
    return () => { alive = false; };
  }, []);

  const generate = useCallback(async () => {
    setBusy(true);
    const issued = await generatePairingCode();
    setBusy(false);
    setFailed(!issued.ok);
    if (issued.ok) {
      setNow(Date.now());
      setCode({ value: issued.data.code, expiresAt: Date.now() + issued.data.seconds_left * 1000 });
    }
  }, []);

  const remaining = code ? Math.max(0, Math.ceil((code.expiresAt - now) / 1000)) : 0;
  useEffect(() => {
    if (!code) return;
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, [code]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- code expiré : la pastille se retire
    if (code && remaining === 0) setCode(null);
  }, [code, remaining]);

  const url = network.localIp ? `http://${network.localIp}:${network.port}` : network.mdnsUrl;
  return (
    <>
      <button type="button" className="btn btn-secondary" disabled={busy} onClick={generate}>
        <Icon name="key" size={16} /> {t(code ? "devices.access.pairingRegenerate" : "devices.access.pairingGenerate")}
      </button>
      {failed && <p className="settings-hint">{t("devices.access.pairingGenerateFailed")}</p>}
      {code && (
        <aside className="pairing-popup glass-floating" role="status" aria-live="polite">
          <button type="button" className="pairing-popup-close" onClick={() => setCode(null)} aria-label={t("common.close")}>
            <Icon name="close" size={16} />
          </button>
          <p className="settings-hint">{url ? t("devices.access.pairingHint", { url }) : t("devices.access.pairingHintNoUrl")}</p>
          <output className="pairing-code-value">{code.value}</output>
          <span className="pairing-code-timer">{t("devices.access.pairingExpiresIn", { time: clock(remaining) })}</span>
        </aside>
      )}
    </>
  );
}

interface ClaimFlowProps {
  pinLength: number;
  onPaired: () => void;
  notify: SectionProps["notify"];
  t: SectionProps["t"];
}

/** Appareil distant : saisie du code lu sur l'écran local, puis choix du PIN. Mêmes composants que le reste de l'onglet. */
export function PairingClaimFlow({ pinLength, onPaired, notify, t }: ClaimFlowProps) {
  const [codeLength, setCodeLength] = useState<number | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [status, setStatus] = useState<PinStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void getPairingStatus().then((res) => {
      if (alive && res.ok) setCodeLength(res.data.code_length);
    });
    return () => { alive = false; };
  }, []);

  /** Le code est contrôlé dès qu'il est saisi : une erreur s'affiche tout de suite, avant le choix du PIN. */
  const checkCode = async (digits: string) => {
    const result = await verifyPairingCode(digits);
    if (result.ok) {
      setMessage(null);
      setCode(digits);
      return;
    }
    setMessage(errorText(result.error, t));
    setStatus("error");
    setTimeout(() => {
      setStatus("idle");
      setResetKey((k) => k + 1);
    }, 520);
  };

  const submitClaim = async (pin: string): Promise<boolean> => {
    const result = await claimPairingCode(code ?? "", pin);
    if (result.ok) {
      notify(t("devices.access.pairingSuccess"), "success");
      onPaired();
      return true;
    }
    notify(errorText(result.error, t), "error");
    if (result.error.code === "bad_pairing_code" || result.error.code === "locked") {
      setCode(null); // le code est à ressaisir
      setResetKey((k) => k + 1);
    }
    return false;
  };

  if (code === null) {
    return (
      <PinEntry
        length={codeLength ?? pinLength}
        status={status}
        caption={message ?? t("devices.access.pairingCodePrompt")}
        resetKey={resetKey}
        onComplete={checkCode}
        labels={pinLabels(t)}
      />
    );
  }
  return <PinSetupFlow length={pinLength} onSubmit={submitClaim} t={t} />;
}
