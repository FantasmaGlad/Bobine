import { useCallback, useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { type MixerView } from "@/lib/devices/routing";
import { RADIO_CHANNELS, type RadioChannelId } from "@/lib/outputs";
import { type RadioMix } from "@/lib/radioMix";
import { type RadioSoundSettings } from "@/lib/radioSound";
import { errorText, type SectionProps } from "../shared/section";
import { type MixPatch } from "./mixPatch";

const SEND_DELAY_MS = 150;

export type MixDrafts = Partial<Record<RadioChannelId, { mix?: RadioMix; sound?: RadioSoundSettings }>>;
type Pending = Partial<Record<RadioChannelId, { mix?: MixPatch; sound?: RadioSoundSettings }>>;

export function useMixerWrites(setDrafts: Dispatch<SetStateAction<MixDrafts>>, notify: SectionProps["notify"], t: SectionProps["t"]) {
  const pending = useRef<Pending>({});
  const timers = useRef<Partial<Record<RadioChannelId, ReturnType<typeof setTimeout>>>>({});
  const writes = useRef<Partial<Record<RadioChannelId, Promise<void>>>>({});
  const revision = useRef<Partial<Record<RadioChannelId, number>>>({});

  const flush = useCallback(async (channel: RadioChannelId) => {
    const body = pending.current[channel];
    pending.current[channel] = undefined;
    if (!body) return;
    const version = (revision.current[channel] ?? 0) + 1;
    revision.current[channel] = version;
    const write = (writes.current[channel] ?? Promise.resolve()).catch(() => {}).then(async () => {
      const result = await devicesRequest<MixerView>(`/mixer/${channel}`, { method: "PUT", body: { mix: body.mix, sound: body.sound } });
      if (revision.current[channel] === version && !pending.current[channel]) setDrafts((current) => ({ ...current, [channel]: undefined }));
      if (!result.ok) notify(errorText(result.error, t), "error");
    });
    writes.current[channel] = write;
    await write;
  }, [notify, t, setDrafts]);

  const flushRef = useRef(flush);
  useEffect(() => { flushRef.current = flush; }, [flush]);
  useEffect(() => () => {
    Object.values(timers.current).forEach((id) => id && clearTimeout(id));
    for (const channel of RADIO_CHANNELS) void flushRef.current(channel);
  }, []);

  const schedule = useCallback((channel: RadioChannelId) => {
    const previous = timers.current[channel];
    if (previous) clearTimeout(previous);
    timers.current[channel] = setTimeout(() => void flush(channel), SEND_DELAY_MS);
  }, [flush]);

  return { pendingRef: pending, schedule };
}
