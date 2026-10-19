"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { devicesRequest, secondsLeft, signalBars, wifiConnectPlan, type WifiNetwork, type WifiStatus } from "@/lib/devicesApi";
import { errorText, openSystemSettings, useDevicesResource, type SectionProps } from "./common";

interface AckRequest {
  kind: "connect" | "forget" | "power";
  ssid?: string;
  password?: string;
  on?: boolean;
}

export default function WifiSection({ caps, local, refreshKey, notify, t }: SectionProps) {
  const { data, error, loading, reload } = useDevicesResource<WifiStatus>("/wifi", refreshKey);
  const [passwordFor, setPasswordFor] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [ack, setAck] = useState<AckRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [forgetting, setForgetting] = useState<string | null>(null);
  // Secondes écoulées depuis la dernière valeur reçue du serveur (compte à rebours local).
  const [elapsed, setElapsed] = useState(0);

  const pending = data?.pending_change ?? null;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- recale le compte à rebours sur la valeur reçue du serveur
    setElapsed(0);
    if (!pending) return;
    const timer = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(timer);
  }, [pending?.seconds_left, pending?.target, pending]);
  const left = secondsLeft(pending, elapsed);
  // Échéance atteinte : le serveur vient de rétablir l'ancien réseau (ou l'a confirmé) — relit l'état.
  useEffect(() => {
    if (pending && left === 0) {
      const timer = setTimeout(() => { void reload(); }, 1500);
      return () => clearTimeout(timer);
    }
  }, [pending, left, reload]);

  const run = async (path: string, body: unknown, request: AckRequest, okMessage?: string) => {
    setBusy(true);
    const result = await devicesRequest(path, { body });
    setBusy(false);
    if (result.ok) {
      if (okMessage) notify(okMessage, "success");
      setPasswordFor(null);
      setPassword("");
      setAck(null);
      await reload();
      return;
    }
    if (result.error.code === "ack_required") {
      setAck(request);
      return;
    }
    notify(errorText(result.error, t), "error");
    await reload();
  };

  const connect = (ssid: string, pw?: string, acknowledged = false) =>
    run("/wifi/connect", { ssid, password: pw || undefined, acknowledge_disconnect: acknowledged }, { kind: "connect", ssid, password: pw }, t("devices.wifi.connecting"));
  const forget = (ssid: string, acknowledged = false) =>
    run("/wifi/forget", { ssid, acknowledge_disconnect: acknowledged }, { kind: "forget", ssid }, t("devices.wifi.forgotten"));
  const power = (on: boolean, acknowledged = false) =>
    run("/wifi/power", { on, acknowledge_disconnect: acknowledged }, { kind: "power", on });

  const confirm = async () => {
    const result = await devicesRequest<{ confirmed: boolean }>("/wifi/confirm", { body: {} });
    if (result.ok) {
      notify(t("devices.wifi.confirmed"), "success");
      await reload();
    } else {
      notify(errorText(result.error, t), "error");
    }
  };

  const proceedAfterAck = () => {
    if (!ack) return;
    if (ack.kind === "connect" && ack.ssid) void connect(ack.ssid, ack.password, true);
    else if (ack.kind === "forget" && ack.ssid) void forget(ack.ssid, true);
    else if (ack.kind === "power") void power(ack.on === true, true);
  };

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error) return <div className="rl-center-note">{errorText(error, t)}</div>;
  if (!data?.supported) {
    return (
      <div className="rl-empty-state">
        <Icon name="wifi_off" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
        <p style={{ margin: 0, fontWeight: 600 }}>{t("devices.wifi.unsupported")}</p>
        {data?.reason && <p className="settings-hint">{data.reason}</p>}
        {caps.system_settings?.supported && (
          <button type="button" className="btn btn-secondary" style={{ marginTop: "12px" }} onClick={() => openSystemSettings("wifi", notify, t)}>
            <Icon name="settings" size={14} /> {t("devices.wifi.openSettings")}
          </button>
        )}
      </div>
    );
  }

  const can = (key: string) => caps[key]?.supported === true;
  const readOnly = data.read_only === true || !can("wifi_connect");
  const current = data.current ?? null;
  const networks = data.networks ?? [];

  const networkRow = (network: WifiNetwork) => {
    const plan = wifiConnectPlan(network, local);
    return (
      <div key={network.ssid} className={`dv-row ${network.in_use ? "active" : ""}`}>
        <span className="dv-icon">
          <Icon name={network.signal >= 75 ? "signal_wifi_4_bar" : network.signal >= 50 ? "network_wifi_3_bar" : network.signal >= 25 ? "network_wifi_2_bar" : "network_wifi_1_bar"} size={22} />
        </span>
        <span className="dv-text">
          <span className="dv-title">
            {network.ssid}
            {network.in_use && <span className="dv-badge">{t("devices.wifi.connected")}</span>}
            {network.known && !network.in_use && <span className="dv-badge dv-badge--muted">{t("devices.wifi.known")}</span>}
          </span>
          <span className="dv-sub">
            {network.security ? <><Icon name="lock" size={12} /> {network.security}</> : t("devices.wifi.open")}
            {network.band ? ` · ${network.band}` : ""} · {signalBars(network.signal)}/4
          </span>
        </span>
        {!readOnly && !network.in_use && (
          <span className="dv-actions">
            {plan === "password_local_only" ? (
              <span className="dv-sub" title={t("devices.wifi.passwordLocalOnly")}><Icon name="lock" size={14} /> {t("devices.wifi.passwordLocalShort")}</span>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy || !!pending}
                onClick={() => (plan === "needs_password" ? (setPasswordFor(network.ssid), setPassword("")) : connect(network.ssid))}
              >
                {t("devices.wifi.connect")}
              </button>
            )}
            {network.known && can("wifi_forget") && (
              forgetting === network.ssid ? (
                <button type="button" className="btn btn-danger" disabled={busy} onClick={() => { setForgetting(null); void forget(network.ssid); }}>
                  {t("devices.wifi.confirmForget")}
                </button>
              ) : (
                <button type="button" className="btn btn-secondary" onClick={() => setForgetting(network.ssid)}>
                  <Icon name="delete" size={14} /> {t("devices.wifi.forget")}
                </button>
              )
            )}
          </span>
        )}
        {passwordFor === network.ssid && (
          <form
            className="dv-password"
            onSubmit={(e) => { e.preventDefault(); void connect(network.ssid, password); }}
          >
            <input
              type="password"
              className="form-control"
              autoFocus
              autoComplete="off"
              placeholder={t("devices.wifi.passwordPlaceholder")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="submit" className="btn btn-primary" disabled={busy || password.length < 8}>{t("devices.wifi.connect")}</button>
            <button type="button" className="btn btn-secondary" onClick={() => { setPasswordFor(null); setPassword(""); }}>{t("devices.wifi.cancel")}</button>
          </form>
        )}
      </div>
    );
  };

  return (
    <div className="dv-section">
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

      <div className="dv-toolbar">
        <span className={`status-pill ${current ? "success" : "neutral"}`}>
          <Icon name={current ? "wifi" : "wifi_off"} size={14} />{" "}
          {current ? (current.ssid ? t("devices.wifi.connectedTo", { ssid: current.ssid }) : t("devices.wifi.connectedUnnamed")) : t("devices.wifi.disconnected")}
        </span>
        {current?.ip && <span className="dv-sub">{current.ip}</span>}
        {data.transport && data.transport !== "wifi" && data.transport !== "none" && (
          <span className="dv-sub">{t("devices.wifi.otherTransport", { transport: data.transport })}</span>
        )}
        <div className="rl-toolbar-spacer" />
        {can("wifi_scan") && data.enabled && (
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={async () => { await devicesRequest("/wifi/scan", { body: {} }); setTimeout(() => { void reload(); }, 2500); }}>
            <Icon name="refresh" size={14} /> {t("devices.wifi.scan")}
          </button>
        )}
        {can("wifi_power") && (
          <button type="button" className="btn btn-secondary" disabled={busy || !!pending} onClick={() => power(!data.enabled)}>
            <Icon name="power_settings_new" size={14} /> {data.enabled ? t("devices.wifi.turnOff") : t("devices.wifi.turnOn")}
          </button>
        )}
        {caps.system_settings?.supported && (
          <button type="button" className="btn btn-secondary" onClick={() => openSystemSettings("wifi", notify, t)}>
            <Icon name="settings" size={14} /> {t("devices.wifi.openSettings")}
          </button>
        )}
      </div>

      {readOnly && <div className="dv-note"><Icon name="info" size={16} /> <span>{caps.wifi_connect?.reason || t("devices.wifi.readOnly")}</span></div>}
      {!readOnly && !local && <div className="dv-note"><Icon name="lock" size={16} /> <span>{t("devices.wifi.passwordLocalOnly")}</span></div>}

      {networks.length > 0 && (
        <>
          <h4 className="rl-block-title">{t("devices.wifi.networks")} <span className="rl-nav-count">{networks.length}</span></h4>
          <div className="dv-list">{networks.map(networkRow)}</div>
        </>
      )}
      {networks.length === 0 && !readOnly && data.enabled && <p className="rl-empty-note">{t("devices.wifi.noNetworks")}</p>}
    </div>
  );
}
