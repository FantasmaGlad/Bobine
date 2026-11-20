import { useState } from "react";
import { balanceFromSlider } from "@/lib/devices/audio";
import { devicesRequest } from "@/lib/devices/request";
import { type AudioDevice } from "@/lib/devices/types";
import { errorText, type SectionProps } from "../../shared/section";

export type Tone = "left" | "right" | "both";

interface Options {
  device: AudioDevice | null;
  notify: SectionProps["notify"];
  t: SectionProps["t"];
  load: () => Promise<void>;
  onClose: () => void;
  onChanged: () => void;
}

function useAliasDraft(device: AudioDevice | null) {
  const [alias, setAlias] = useState(device?.alias ?? "");
  const aliasKey = `${device?.id}|${device?.alias}`;
  const [aliasFor, setAliasFor] = useState(aliasKey);
  if (aliasFor !== aliasKey) {
    setAliasFor(aliasKey);
    setAlias(device?.alias ?? "");
  }
  return { alias, setAlias };
}

export function useAudioDetailActions({ device, notify, t, load, onClose, onChanged }: Options) {
  const [sliding, setSliding] = useState<number | null>(null);
  const [playing, setPlaying] = useState<Tone | null>(null);
  const { alias, setAlias } = useAliasDraft(device);

  const call = async (path: string, body: unknown, method = "POST") => {
    const result = await devicesRequest(path, { method, body });
    if (!result.ok) notify(errorText(result.error, t), "error");
    return result.ok;
  };

  const commitBalance = async (value: number) => {
    const ok = await call("/audio/balance", { id: device!.id, balance: balanceFromSlider(value) });
    setSliding(null);
    if (ok) await load();
  };

  const playTone = async (channel: Tone) => {
    setPlaying(channel);
    await call("/audio/test", { id: device!.id, channel });
    setPlaying(null);
  };

  const saveAlias = async () => {
    if ((alias.trim() || null) === (device!.alias ?? null)) return;
    if (await call("/audio/meta", { id: device!.id, alias: alias.trim() }, "PUT")) {
      notify(t("devices.audio.detail.nameSaved"), "success");
      onChanged();
    }
  };

  const toggleHidden = async () => {
    const hide = !device!.hidden;
    if (await call("/audio/meta", { id: device!.id, hidden: hide }, "PUT")) {
      notify(hide ? t("devices.audio.detail.nowHidden") : t("devices.audio.detail.nowShown"), "success");
      onChanged();
      if (hide) onClose();
    }
  };

  const selectProfile = async (index: number) => {
    if (await call("/audio/profile", { id: device!.id, index })) {
      await load();
      onChanged();
    }
  };

  return { sliding, setSliding, playing, alias, setAlias, commitBalance, playTone, saveAlias, toggleHidden, selectProfile };
}

export type AudioDetailActions = ReturnType<typeof useAudioDetailActions>;
