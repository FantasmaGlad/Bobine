"use client";

import Icon from "@/components/Icon";
import { bluetoothKindIcon } from "@/lib/devices/wireless";
import { type BluetoothDevice } from "@/lib/devices/types";
import { type SectionProps } from "../shared/section";
import { type BluetoothCall } from "./useBluetoothCall";

interface RowProps {
  device: BluetoothDevice;
  can: (key: string) => boolean;
  busy: boolean;
  pairing: boolean;
  forgetting: string | null;
  setForgetting: (address: string | null) => void;
  call: BluetoothCall;
  t: SectionProps["t"];
}

function DeviceText({ device, t }: { device: BluetoothDevice; t: SectionProps["t"] }) {
  return (
    <span className="dv-text">
      <span className="dv-title">
        {device.name}
        {device.connected && <span className="dv-badge">{t("devices.bluetooth.connected")}</span>}
      </span>
      <span className="dv-sub">
        {device.address}
        {device.profiles.length > 0 ? ` · ${device.profiles.join(", ")}` : ""}
        {device.battery !== null ? ` · ${device.battery} %` : ""}
        {!device.paired && device.rssi !== null ? ` · ${device.rssi} dBm` : ""}
      </span>
    </span>
  );
}

function ForgetButton({ device, busy, forgetting, setForgetting, call, t }: RowProps) {
  if (forgetting === device.address) {
    return (
      <button type="button" className="btn btn-danger" disabled={busy} onClick={() => { setForgetting(null); void call("/bluetooth/forget", { address: device.address }, t("devices.bluetooth.forgotten")); }}>
        {t("devices.bluetooth.confirmForget")}
      </button>
    );
  }
  return (
    <button type="button" className="btn btn-secondary" onClick={() => setForgetting(device.address)}>
      <Icon name="delete" size={14} /> {t("devices.bluetooth.forget")}
    </button>
  );
}

function DeviceActions(props: RowProps) {
  const { device, can, busy, pairing, call, t } = props;
  return (
    <span className="dv-actions">
      {!device.paired && can("bluetooth_pair") && (
        <button type="button" className="btn btn-primary" disabled={busy || pairing} onClick={() => call("/bluetooth/pair", { address: device.address })}>
          <Icon name="link" size={14} /> {t("devices.bluetooth.pair")}
        </button>
      )}
      {device.paired && can("bluetooth_connect") && (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => call(device.connected ? "/bluetooth/disconnect" : "/bluetooth/connect", { address: device.address })}
        >
          {device.connected ? t("devices.bluetooth.disconnect") : t("devices.bluetooth.connect")}
        </button>
      )}
      {device.paired && can("bluetooth_forget") && <ForgetButton {...props} />}
    </span>
  );
}

export default function BluetoothDeviceRow(props: RowProps) {
  const { device, t } = props;
  return (
    <div data-focus-id={device.address} className={`dv-row glass-interactive ${device.connected ? "active" : ""}`}>
      <span className="dv-icon"><Icon name={bluetoothKindIcon(device.kind)} size={22} /></span>
      <DeviceText device={device} t={t} />
      <DeviceActions {...props} />
    </div>
  );
}
