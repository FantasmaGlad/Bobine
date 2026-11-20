"use client";

import { useState } from "react";
import { splitBluetooth } from "@/lib/devices/wireless";
import { type BluetoothDevice, type BluetoothStatus } from "@/lib/devices/types";
import { errorText, type SectionProps } from "./shared/section";
import { useDevicesResource } from "./shared/useDevicesResource";
import { useFocusFlash } from "./shared/useFocusFlash";
import { BluetoothPermission, BluetoothUnsupported } from "./bluetooth/BluetoothFallbacks";
import BluetoothDeviceRow from "./bluetooth/BluetoothDeviceRow";
import BluetoothNotes from "./bluetooth/BluetoothNotes";
import BluetoothToolbar from "./bluetooth/BluetoothToolbar";
import { useBluetoothCall, useDiscoveryPolling } from "./bluetooth/useBluetoothCall";

export default function BluetoothSection({ caps, refreshKey, notify, t, focusId, focusNonce }: SectionProps) {
  const { data, error, loading, reload } = useDevicesResource<BluetoothStatus>("/bluetooth", refreshKey);
  const [forgetting, setForgetting] = useState<string | null>(null);
  const { busy, call } = useBluetoothCall(notify, t, reload);
  useFocusFlash(focusId, focusNonce, !!data?.supported);
  const discovering = data?.discovering === true;
  useDiscoveryPolling(discovering, reload);

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error) return <div className="rl-center-note">{errorText(error, t)}</div>;
  if (!data?.supported) return <BluetoothUnsupported reason={data?.reason} t={t} />;
  if (data.permission_required) return <BluetoothPermission message={data.permission_message} call={call} t={t} />;

  const { paired, nearby } = splitBluetooth(data.devices ?? []);
  const can = (key: string) => caps[key]?.supported === true;
  const pairing = data.pairing?.state === "pairing";
  const deviceRow = (device: BluetoothDevice) => (
    <BluetoothDeviceRow
      key={device.address}
      device={device}
      can={can}
      busy={busy}
      pairing={pairing}
      forgetting={forgetting}
      setForgetting={setForgetting}
      call={call}
      t={t}
    />
  );

  return (
    <div className="dv-section">
      <BluetoothToolbar data={data} can={can} systemSettings={!!caps.system_settings?.supported} discovering={discovering} busy={busy} call={call} notify={notify} t={t} />
      <BluetoothNotes data={data} caps={caps} can={can} call={call} t={t} />
      <h4 className="rl-block-title">{t("devices.bluetooth.paired")} <span className="rl-nav-count">{paired.length}</span></h4>
      {paired.length === 0 ? <p className="rl-empty-note">{t("devices.bluetooth.noPaired")}</p> : <div className="dv-list">{paired.map(deviceRow)}</div>}
      {(nearby.length > 0 || discovering) && (
        <>
          <h4 className="rl-block-title">{t("devices.bluetooth.nearby")} <span className="rl-nav-count">{nearby.length}</span></h4>
          {nearby.length === 0 ? <p className="rl-empty-note">{t("devices.bluetooth.searching")}</p> : <div className="dv-list">{nearby.map(deviceRow)}</div>}
        </>
      )}
    </div>
  );
}
