"use client";

import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import { audioDisplayName, audioKindIcon } from "@/lib/devices/audio";
import { type AudioDevice } from "@/lib/devices/types";
import { AnalysisBlock, BalanceBlock, NameBlock, ProfileBlock, ToneBlock } from "./audio/detail/AudioDetailBlocks";
import { useAudioDetailActions } from "./audio/detail/useAudioDetailActions";
import { useAudioDetails } from "./audio/detail/useAudioDetails";
import { type SectionProps } from "./common";

interface Props extends Pick<SectionProps, "caps" | "notify" | "t"> {
  device: AudioDevice | null;
  onClose: () => void;
  onChanged: () => void;
}

function DetailHead({ device, t }: { device: AudioDevice; t: SectionProps["t"] }) {
  return (
    <div className="dv-detail-head">
      <span className="dv-icon"><Icon name={audioKindIcon(device.kind)} size={24} /></span>
      <span className="dv-sub">
        {t(`devices.audio.kind.${device.kind}`)}
        {device.manufacturer ? ` · ${device.manufacturer}` : ""}
        {device.alias ? ` · ${device.name}` : ""}
      </span>
      {device.is_default && <span className="dv-badge">{t("devices.audio.default")}</span>}
    </div>
  );
}

export default function AudioDetailSheet({ device, caps, notify, t, onClose, onChanged }: Props) {
  const { details, failed, load } = useAudioDetails(device?.id ?? null, t);
  const actions = useAudioDetailActions({ device, notify, t, load, onClose, onChanged });

  if (!device) return null;
  const can = (key: string) => caps[key]?.supported === true;
  const balance = details?.balance ?? null;

  return (
    <Sheet open onClose={onClose} tall title={audioDisplayName(device)} closeLabel={t("devices.audio.detail.close")}>
      <div className="dv-detail">
        <DetailHead device={device} t={t} />
        {failed && <div className="dv-note"><Icon name="error" size={16} /><span>{failed}</span></div>}
        {can("audio_balance") && balance !== null && <BalanceBlock balance={balance} actions={actions} t={t} />}
        {can("audio_test_tone") && <ToneBlock actions={actions} t={t} />}
        <AnalysisBlock details={details} failed={failed} t={t} />
        {can("audio_profile") && details && details.profiles.length > 0 && <ProfileBlock details={details} actions={actions} t={t} />}
        <NameBlock device={device} actions={actions} t={t} />
      </div>
    </Sheet>
  );
}
