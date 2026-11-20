"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import { type AudioDevice, type AudioListing } from "@/lib/devices/types";
import AudioDetailSheet from "./AudioDetailSheet";
import AudioDeviceRow from "./audio/AudioDeviceRow";
import { AudioUnsupported, NoDefaultSwitchNote } from "./audio/AudioNotes";
import { useAudioCalls } from "./audio/useAudioCalls";
import { errorText, type SectionProps } from "./shared/section";
import { useDevicesResource } from "./shared/useDevicesResource";
import { useFocusFlash } from "./shared/useFocusFlash";

export default function AudioSection({ caps, refreshKey, notify, t, focusId, focusNonce }: SectionProps) {
  const { data, error, loading, reload } = useDevicesResource<AudioListing>("/audio", refreshKey);
  const calls = useAudioCalls(notify, t, reload);
  const [openId, setOpenId] = useState<string | null>(null);
  const [showHidden, setShowHidden] = useState(false);

  const focusRequest = focusId ? `${focusId}|${focusNonce}` : null;
  const [openedFor, setOpenedFor] = useState<string | null>(null);
  if (focusId && focusRequest && focusRequest !== openedFor && data?.devices?.some((d) => d.id === focusId)) {
    setOpenedFor(focusRequest);
    setOpenId(focusId);
  }
  useFocusFlash(focusId, focusNonce, !!data?.supported);

  const canDefault = !!caps.audio_set_default?.supported;
  const canVolume = !!caps.audio_set_volume?.supported;

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error) return <div className="rl-center-note">{errorText(error, t)}</div>;
  if (!data?.supported) return <AudioUnsupported reason={data?.reason} t={t} />;

  const all = data.devices ?? [];
  const devices = all.filter((d) => !d.hidden);
  const hiddenDevices = all.filter((d) => d.hidden);
  const opened = all.find((d) => d.id === openId) ?? null;
  const renderRow = (device: AudioDevice) => (
    <AudioDeviceRow key={device.id} device={device} selected={openId === device.id} canVolume={canVolume} canDefault={canDefault} calls={calls} onOpen={setOpenId} t={t} />
  );

  return (
    <div className="dv-section">
      {!canDefault && <NoDefaultSwitchNote caps={caps} notify={notify} t={t} />}
      {devices.length === 0 ? <p className="rl-empty-note">{t("devices.audio.none")}</p> : <div className="dv-list">{devices.map(renderRow)}</div>}
      {hiddenDevices.length > 0 && (
        <div className="dv-hidden">
          <button type="button" className="dv-link-btn" aria-expanded={showHidden} onClick={() => setShowHidden((v) => !v)}>
            <Icon name={showHidden ? "expand_less" : "expand_more"} size={14} /> {t("devices.audio.hiddenOutputs", { count: hiddenDevices.length })}
          </button>
          {showHidden && <div className="dv-list">{hiddenDevices.map(renderRow)}</div>}
        </div>
      )}
      <AudioDetailSheet device={opened} caps={caps} notify={notify} t={t} onClose={() => setOpenId(null)} onChanged={() => { void reload(); }} />
    </div>
  );
}
