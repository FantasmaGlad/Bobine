import type { OutputId } from "../outputs.ts";

export function videoSoundSavePath(channel: OutputId): string {
  return `/outputs/${channel}/playback/set_sound`;
}
