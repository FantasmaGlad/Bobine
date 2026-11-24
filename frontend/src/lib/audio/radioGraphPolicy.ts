import type { RadioRoute } from "../audioRoute.ts";
import { isNeutralMix, type RadioMix } from "../radioMix.ts";
import { isNeutralSound, type RadioSoundSettings } from "../radioSound.ts";

export function needsWebAudioGraph(
  sound: RadioSoundSettings,
  mix: RadioMix,
  route: RadioRoute | null,
  meter: boolean,
): boolean {
  return !isNeutralSound(sound) || !isNeutralMix(mix) || route !== null || meter;
}
