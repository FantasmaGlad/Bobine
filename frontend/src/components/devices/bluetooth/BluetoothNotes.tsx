"use client";

import Icon from "@/components/Icon";
import { type BluetoothStatus, type Capabilities } from "@/lib/devices/types";
import { type SectionProps } from "../common";
import { type BluetoothCall } from "./useBluetoothCall";

interface NotesProps {
  data: BluetoothStatus;
  caps: Capabilities;
  can: (key: string) => boolean;
  call: BluetoothCall;
  t: SectionProps["t"];
}

function PairingRequest({ data, call, t }: NotesProps) {
  const pending = data.pending_pairing!;
  return (
    <div className="dv-note dv-note--strong" role="alertdialog" aria-label={t("devices.bluetooth.pairingRequest")}>
      <Icon name="key" size={18} />
      <span>
        <strong>{pending.name}</strong> — {pending.passkey ? t("devices.bluetooth.confirmCode") : t("devices.bluetooth.authorizeRequest")}
        {pending.passkey && <span className="dv-passkey">{pending.passkey}</span>}
      </span>
      <button type="button" className="btn btn-primary" onClick={() => call("/bluetooth/pairing/respond", { address: pending.address, accept: true })}>
        <Icon name="check" size={14} /> {t("devices.bluetooth.accept")}
      </button>
      <button type="button" className="btn btn-secondary" onClick={() => call("/bluetooth/pairing/respond", { address: pending.address, accept: false })}>
        {t("devices.bluetooth.refuse")}
      </button>
    </div>
  );
}

export default function BluetoothNotes(props: NotesProps) {
  const { data, caps, can, t } = props;
  const pending = data.pending_pairing ?? null;
  const progress = data.pairing ?? null;
  return (
    <>
      {pending && <PairingRequest {...props} />}
      {!pending && progress?.state === "pairing" && (
        <div className="dv-note"><Icon name="sync" size={16} className="olc-spin" /> <span>{t("devices.bluetooth.pairing")}</span></div>
      )}
      {!pending && progress?.state === "failed" && (
        <div className="dv-note"><Icon name="error" size={16} /> <span>{progress.error || t("devices.bluetooth.pairFailed")}</span></div>
      )}
      {caps.bluetooth_connect && !can("bluetooth_connect") && (
        <div className="dv-note"><Icon name="info" size={16} /> <span>{caps.bluetooth_connect.reason}</span></div>
      )}
    </>
  );
}
