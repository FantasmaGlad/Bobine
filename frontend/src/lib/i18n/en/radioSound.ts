import type { Dict } from "../core.ts";

export const radioSound: Dict = {
  title: "Sound",
  enabledOn: "On",
  enabledOff: "Neutral sound",
  enabledHint: "Turn the equalizer off: the sound is played as is, with no processing.",
  presetsLabel: "Presets",
  presets: {
    bass: "Bass Boost",
    voice: "Voice Boost",
    soft: "Soften",
  },
  bandsLabel: "5-band equalizer",
  bass: "Bass",
  loudness: "Loudness",
  loudnessHint: "Raises low and high frequencies at low volume.",
  limiter: "Overload protection",
  limiterHint: "Avoids distortion when the settings strongly raise the sound.",
  reset: "Reset",
};
