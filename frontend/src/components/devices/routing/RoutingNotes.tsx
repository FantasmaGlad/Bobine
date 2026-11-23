"use client";

import Icon from "@/components/Icon";
import { type SectionProps } from "../shared/section";

async function unlockOutputLabels(): Promise<"ok" | "denied" | "unsupported"> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return "unsupported";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return "ok";
  } catch {
    return "denied";
  }
}

export function UnlockLabelsNote({ notify, t }: { notify: SectionProps["notify"]; t: SectionProps["t"] }) {
  const unlock = async () => {
    const outcome = await unlockOutputLabels();
    notify(t(`devices.routing.unlock.${outcome}`), outcome === "ok" ? "success" : "warning");
  };
  return (
    <div className="dv-note dv-note--strong">
      <Icon name="visibility" size={16} />
      <span>{t("devices.routing.unlock.hint")}</span>
      <button type="button" className="btn btn-secondary" onClick={() => void unlock()}>
        <Icon name="mic" size={14} /> {t("devices.routing.unlock.button")}
      </button>
    </div>
  );
}
