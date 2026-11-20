"use client";

import Icon from "@/components/Icon";
import { type WifiPendingChange } from "@/lib/devices/types";
import { type SectionProps } from "../shared/section";
import { type WifiActions } from "./useWifiActions";

interface BannersProps {
  pending: WifiPendingChange | null;
  left: number;
  actions: WifiActions;
  t: SectionProps["t"];
}

export default function WifiBanners({ pending, left, actions, t }: BannersProps) {
  const { ack, setAck, busy, confirm, proceedAfterAck } = actions;
  return (
    <>
      {pending && (
        <div className="dv-note dv-note--strong" role="alert">
          <Icon name="timer" size={18} />
          <span>
            {t("devices.wifi.pendingBody", { target: pending.target, seconds: left })}
            {pending.previous ? ` ${t("devices.wifi.pendingPrevious", { previous: pending.previous })}` : ""}
          </span>
          <button type="button" className="btn btn-primary" onClick={confirm}>
            <Icon name="check" size={14} /> {t("devices.wifi.confirmChange")}
          </button>
        </div>
      )}
      {ack && (
        <div className="dv-note dv-note--strong" role="alertdialog">
          <Icon name="warning" size={18} />
          <span>{t("devices.wifi.ackBody")}</span>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={proceedAfterAck}>{t("devices.wifi.ackContinue")}</button>
          <button type="button" className="btn btn-secondary" onClick={() => setAck(null)}>{t("devices.wifi.cancel")}</button>
        </div>
      )}
    </>
  );
}
