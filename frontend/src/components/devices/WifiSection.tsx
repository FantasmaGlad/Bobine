"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import { type WifiStatus } from "@/lib/devices/types";
import { errorText, type SectionProps } from "./shared/section";
import { useDevicesResource } from "./shared/useDevicesResource";
import { useFocusFlash } from "./shared/useFocusFlash";
import { usePendingCountdown } from "./wifi/usePendingCountdown";
import { useWifiActions } from "./wifi/useWifiActions";
import WifiBanners from "./wifi/WifiBanners";
import WifiNetworkRow from "./wifi/WifiNetworkRow";
import WifiToolbar from "./wifi/WifiToolbar";
import WifiUnsupported from "./wifi/WifiUnsupported";

export default function WifiSection({ caps, local, refreshKey, notify, t, focusId, focusNonce }: SectionProps) {
  const { data, error, loading, reload } = useDevicesResource<WifiStatus>("/wifi", refreshKey);
  const actions = useWifiActions(notify, t, reload);
  const [forgetting, setForgetting] = useState<string | null>(null);
  useFocusFlash(focusId, focusNonce, !!data?.supported);
  const pending = data?.pending_change ?? null;
  const left = usePendingCountdown(pending, reload);
  const systemSettings = !!caps.system_settings?.supported;

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error) return <div className="rl-center-note">{errorText(error, t)}</div>;
  if (!data?.supported) return <WifiUnsupported reason={data?.reason} systemSettings={systemSettings} notify={notify} t={t} />;

  const can = (key: string) => caps[key]?.supported === true;
  const readOnly = data.read_only === true || !can("wifi_connect");
  const networks = data.networks ?? [];

  return (
    <div className="dv-section">
      <WifiBanners pending={pending} left={left} actions={actions} t={t} />
      <WifiToolbar data={data} can={can} systemSettings={systemSettings} pending={!!pending} actions={actions} reload={reload} notify={notify} t={t} />
      {readOnly && <div className="dv-note"><Icon name="info" size={16} /> <span>{caps.wifi_connect?.reason || t("devices.wifi.readOnly")}</span></div>}
      {!readOnly && !local && <div className="dv-note"><Icon name="lock" size={16} /> <span>{t("devices.wifi.passwordLocalOnly")}</span></div>}
      {networks.length > 0 && (
        <>
          <h4 className="rl-block-title">{t("devices.wifi.networks")} <span className="rl-nav-count">{networks.length}</span></h4>
          <div className="dv-list">
            {networks.map((network) => (
              <WifiNetworkRow
                key={network.ssid}
                network={network}
                local={local}
                readOnly={readOnly}
                canForget={can("wifi_forget")}
                pending={!!pending}
                forgetting={forgetting}
                setForgetting={setForgetting}
                actions={actions}
                t={t}
              />
            ))}
          </div>
        </>
      )}
      {networks.length === 0 && !readOnly && data.enabled && <p className="rl-empty-note">{t("devices.wifi.noNetworks")}</p>}
    </div>
  );
}
