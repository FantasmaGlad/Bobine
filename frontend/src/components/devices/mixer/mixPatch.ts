import { type RadioMix } from "@/lib/radioMix";

export type MixPatch = { master?: Partial<RadioMix["master"]>; music?: Partial<RadioMix["music"]>; announcements?: Partial<RadioMix["announcements"]> };

export function mergePatch(a: MixPatch, b: MixPatch): MixPatch {
  return { master: { ...a.master, ...b.master }, music: { ...a.music, ...b.music }, announcements: { ...a.announcements, ...b.announcements } };
}
