"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { initialSetFlow, submitSetCode, type SetFlow } from "@/lib/pinEntry";
import PinEntry, { type PinStatus } from "./PinEntry";
import { pinLabels } from "./pinLabels";
import type { SectionProps } from "./common";

interface PinSetupFlowProps {
  length: number;
  /** Reçoit le PIN confirmé ; vrai si l'enregistrement a réussi (laisse l'animation de succès aller au bout). */
  onSubmit: (pin: string) => Promise<boolean>;
  disabled?: boolean;
  t: SectionProps["t"];
}

/** Définition d'un PIN en deux temps (nouveau code, puis confirmation) : une seule implémentation pour
 *  la sécurité, l'activation locale et l'appairage distant. */
export default function PinSetupFlow({ length, onSubmit, disabled = false, t }: PinSetupFlowProps) {
  const [flow, setFlow] = useState<SetFlow>(initialSetFlow);
  const [status, setStatus] = useState<PinStatus>("idle");
  const [resetKey, setResetKey] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  const restart = useCallback((next: SetFlow, delay: number) => {
    timers.current.push(
      setTimeout(() => {
        setFlow(next);
        setStatus("idle");
        setResetKey((k) => k + 1);
      }, delay),
    );
  }, []);

  const onComplete = async (code: string) => {
    const result = submitSetCode(flow, code);
    if (result.kind === "next") {
      setFlow(result.flow);
      setResetKey((k) => k + 1);
    } else if (result.kind === "mismatch") {
      setStatus("error");
      restart(result.flow, 520);
    } else {
      setStatus("success");
      const saved = await onSubmit(result.pin);
      restart(initialSetFlow, saved ? 700 : 100);
    }
  };

  const caption = flow.mismatch ? t("devices.pin.mismatch") : flow.phase === "new" ? t("devices.pin.new") : t("devices.pin.confirm");
  return (
    <div key={flow.phase} className="pin-slide">
      <PinEntry length={length} status={status} caption={caption} resetKey={resetKey} disabled={disabled} onComplete={onComplete} labels={pinLabels(t)} />
    </div>
  );
}
