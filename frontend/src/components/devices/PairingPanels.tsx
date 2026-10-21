"use client";

import { useCallback, useEffect, useState } from "react";
import { claimPairingCode, generatePairingCode, getPairingStatus } from "@/lib/devicesApi";
import { useAppSettings } from "@/lib/AppSettingsContext";
import PinEntry from "./PinEntry";
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

/** Écran local sans navigateur (Android TV) : code d'association à saisir depuis un autre appareil. */
export function PairingCodeDisplay({ t }: { t: SectionProps["t"] }) {
  const { network } = useAppSettings();
  const [code, setCode] = useState<ActiveCode | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const refresh = useCallback(async () => {
    const status = await getPairingStatus();
    if (status.ok && status.data.code) {
      setCode({ value: status.data.code, expiresAt: Date.now() + status.data.seconds_left * 1000 });
      return;
    }
    const issued = await generatePairingCode();
    if (issued.ok) setCode({ value: issued.data.code, expiresAt: Date.now() + issued.data.seconds_left * 1000 });
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronisation avec le serveur (code d'association)
    void refresh();
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, [refresh]);

  const remaining = code ? Math.max(0, Math.ceil((code.expiresAt - now) / 1000)) : 0;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- code expiré : on en émet un nouveau
    if (code && remaining === 0) void refresh();
  }, [code, remaining, refresh]);

  if (!code) return null;
  const url = network.localIp ? `http://${network.localIp}:${network.port}` : network.mdnsUrl;
  return (
    <div className="pairing-code">
      <p className="settings-hint">{url ? t("devices.access.pairingHint", { url }) : t("devices.access.pairingHintNoUrl")}</p>
      <output className="pairing-code-value" aria-live="off">{code.value}</output>
      <span className="pairing-code-timer">{t("devices.access.pairingExpiresIn", { time: clock(remaining) })}</span>
    </div>
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

  useEffect(() => {
    let alive = true;
    void getPairingStatus().then((res) => {
      if (alive && res.ok) setCodeLength(res.data.code_length);
    });
    return () => { alive = false; };
  }, []);

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
        caption={t("devices.access.pairingCodePrompt")}
        resetKey={resetKey}
        onComplete={(digits) => setCode(digits)}
        labels={pinLabels(t)}
      />
    );
  }
  return <PinSetupFlow length={pinLength} onSubmit={submitClaim} t={t} />;
}
