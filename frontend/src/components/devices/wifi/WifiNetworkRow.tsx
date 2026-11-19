"use client";

import Icon from "@/components/Icon";
import { signalBars, wifiConnectPlan } from "@/lib/devices/wireless";
import { type WifiNetwork } from "@/lib/devices/types";
import { type SectionProps } from "../common";
import { type WifiActions } from "./useWifiActions";

interface RowProps {
  network: WifiNetwork;
  local: boolean;
  readOnly: boolean;
  canForget: boolean;
  pending: boolean;
  forgetting: string | null;
  setForgetting: (ssid: string | null) => void;
  actions: WifiActions;
  t: SectionProps["t"];
}

function signalIcon(signal: number): string {
  if (signal >= 75) return "signal_wifi_4_bar";
  if (signal >= 50) return "network_wifi_3_bar";
  if (signal >= 25) return "network_wifi_2_bar";
  return "network_wifi_1_bar";
}

function NetworkText({ network, t }: { network: WifiNetwork; t: SectionProps["t"] }) {
  return (
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
  );
}

function ForgetButton({ network, forgetting, setForgetting, actions, t }: RowProps) {
  if (forgetting === network.ssid) {
    return (
      <button type="button" className="btn btn-danger" disabled={actions.busy} onClick={() => { setForgetting(null); void actions.forget(network.ssid); }}>
        {t("devices.wifi.confirmForget")}
      </button>
    );
  }
  return (
    <button type="button" className="btn btn-secondary" onClick={() => setForgetting(network.ssid)}>
      <Icon name="delete" size={14} /> {t("devices.wifi.forget")}
    </button>
  );
}

function RowActions(props: RowProps) {
  const { network, local, canForget, pending, actions, t } = props;
  const plan = wifiConnectPlan(network, local);
  return (
    <span className="dv-actions">
      {plan === "password_local_only" ? (
        <span className="dv-sub" title={t("devices.wifi.passwordLocalOnly")}><Icon name="lock" size={14} /> {t("devices.wifi.passwordLocalShort")}</span>
      ) : (
        <button
          type="button"
          className="btn btn-primary"
          disabled={actions.busy || pending}
          onClick={() => (plan === "needs_password" ? (actions.setPasswordFor(network.ssid), actions.setPassword("")) : actions.connect(network.ssid))}
        >
          {t("devices.wifi.connect")}
        </button>
      )}
      {network.known && canForget && <ForgetButton {...props} />}
    </span>
  );
}

function PasswordForm({ network, actions, t }: RowProps) {
  const { password, setPassword, setPasswordFor, busy, connect } = actions;
  return (
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
  );
}

export default function WifiNetworkRow(props: RowProps) {
  const { network, readOnly, actions, t } = props;
  return (
    <div data-focus-id={network.ssid} className={`dv-row glass-interactive ${network.in_use ? "active" : ""}`}>
      <span className="dv-icon">
        <Icon name={signalIcon(network.signal)} size={22} />
      </span>
      <NetworkText network={network} t={t} />
      {!readOnly && !network.in_use && <RowActions {...props} />}
      {actions.passwordFor === network.ssid && <PasswordForm {...props} />}
    </div>
  );
}
