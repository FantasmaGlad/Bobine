"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { bluetoothKindIcon, devicesRequest, splitBluetooth, type BluetoothDevice, type BluetoothStatus } from "@/lib/devicesApi";
import { errorText, openSystemSettings, useDevicesResource, type SectionProps } from "./common";

export default function BluetoothSection({ caps, refreshKey, notify, t }: SectionProps) {
  const { data, error, loading, reload } = useDevicesResource<BluetoothStatus>("/bluetooth", refreshKey);
  const [forgetting, setForgetting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const discovering = data?.discovering === true;
  // Pendant une recherche, relit la liste toutes les 3 s (les nouveaux appareils arrivent au fil de l'eau).
  useEffect(() => {
    if (!discovering) return;
    const timer = setInterval(() => { void reload(); }, 3000);
    return () => clearInterval(timer);
  }, [discovering, reload]);

  const call = async (path: string, body?: unknown, okMessage?: string) => {
    setBusy(true);
    const result = await devicesRequest(path, { method: "POST", body: body ?? {} });
    setBusy(false);
    if (result.ok) {
      if (okMessage) notify(okMessage, "success");
      await reload();
    } else {
      notify(errorText(result.error, t), "error");
      await reload();
    }
  };

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error) return <div className="rl-center-note">{errorText(error, t)}</div>;
  if (!data?.supported) {
    return (
      <div className="rl-empty-state">
        <Icon name="bluetooth_disabled" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
        <p style={{ margin: 0, fontWeight: 600 }}>{t("devices.bluetooth.unsupported")}</p>
        {data?.reason && <p className="settings-hint">{data.reason}</p>}
      </div>
    );
  }

  if (data.permission_required) {
    return (
      <div className="dv-section">
        <div className="dv-note dv-note--strong">
          <Icon name="bluetooth_searching" size={18} />
          <span>{data.permission_message || t("devices.bluetooth.permissionBody")}</span>
          <button type="button" className="btn btn-primary" onClick={() => call("/bluetooth/permission")}>
            <Icon name="check" size={14} /> {t("devices.bluetooth.permissionButton")}
          </button>
        </div>
      </div>
    );
  }

  const { paired, nearby } = splitBluetooth(data.devices ?? []);
  const pending = data.pending_pairing ?? null;
  const progress = data.pairing ?? null;
  const can = (key: string) => caps[key]?.supported === true;

  const deviceRow = (device: BluetoothDevice) => (
    <div key={device.address} className={`dv-row glass-interactive ${device.connected ? "active" : ""}`}>
      <span className="dv-icon"><Icon name={bluetoothKindIcon(device.kind)} size={22} /></span>
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
      <span className="dv-actions">
        {!device.paired && can("bluetooth_pair") && (
          <button type="button" className="btn btn-primary" disabled={busy || progress?.state === "pairing"} onClick={() => call("/bluetooth/pair", { address: device.address })}>
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
        {device.paired && can("bluetooth_forget") && (
          forgetting === device.address ? (
            <button type="button" className="btn btn-danger" disabled={busy} onClick={() => { setForgetting(null); void call("/bluetooth/forget", { address: device.address }, t("devices.bluetooth.forgotten")); }}>
              {t("devices.bluetooth.confirmForget")}
            </button>
          ) : (
            <button type="button" className="btn btn-secondary" onClick={() => setForgetting(device.address)}>
              <Icon name="delete" size={14} /> {t("devices.bluetooth.forget")}
            </button>
          )
        )}
      </span>
    </div>
  );

  return (
    <div className="dv-section">
      <div className="dv-toolbar">
        <span className={`status-pill ${data.powered ? "success" : "neutral"}`}>
          <Icon name={data.powered ? "bluetooth" : "bluetooth_disabled"} size={14} /> {data.powered ? t("devices.bluetooth.on") : t("devices.bluetooth.off")}
        </span>
        {data.adapter_name && <span className="dv-sub">{data.adapter_name}</span>}
        <div className="rl-toolbar-spacer" />
        {can("bluetooth_power") && (
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => call("/bluetooth/power", { on: !data.powered })}>
            <Icon name="power_settings_new" size={14} /> {data.powered ? t("devices.bluetooth.turnOff") : t("devices.bluetooth.turnOn")}
          </button>
        )}
        {can("bluetooth_scan") && data.powered && (
          <button type="button" className={`btn ${discovering ? "btn-primary" : "btn-secondary"}`} disabled={busy} onClick={() => call("/bluetooth/scan", { on: !discovering })}>
            <Icon name="bluetooth_searching" size={14} className={discovering ? "olc-spin" : ""} /> {discovering ? t("devices.bluetooth.stopScan") : t("devices.bluetooth.scan")}
          </button>
        )}
        {caps.system_settings?.supported && (
          <button type="button" className="btn btn-secondary" onClick={() => openSystemSettings("bluetooth", notify, t)}>
            <Icon name="settings" size={14} /> {t("devices.bluetooth.openSettings")}
          </button>
        )}
      </div>

      {pending && (
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
      )}
      {!pending && progress?.state === "pairing" && (
        <div className="dv-note"><Icon name="sync" size={16} className="olc-spin" /> <span>{t("devices.bluetooth.pairing")}</span></div>
      )}
      {!pending && progress?.state === "failed" && (
        <div className="dv-note"><Icon name="error" size={16} /> <span>{progress.error || t("devices.bluetooth.pairFailed")}</span></div>
      )}
      {caps.bluetooth_connect && !can("bluetooth_connect") && (
        <div className="dv-note"><Icon name="info" size={16} /> <span>{caps.bluetooth_connect.reason}</span></div>
      )}

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
