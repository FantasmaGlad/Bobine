import type { Dict } from "../core.ts";

export const mediaNative: Dict = {
  section: "Native audio component (experimental)",
  hint: "Reads the tags, duration and cover art of new tracks with a small built-in program instead of starting ffmpeg for every file: audio library imports are faster and lighter. Off by default. Tracks already imported do not change, and if the component is missing, fails or does not recognise a file, Bobine uses the usual method: no track is ever lost.",
  label: "Enable the native audio component (experimental)",
  state_disabled: "Status: off. Bobine uses the usual method.",
  state_active: "Status: active, supported formats are read natively.",
  state_fallback: "Status: fallback. The component is present but does not answer; the usual method is used.",
  state_absent: "Status: missing. This package does not contain the component; the usual method is used.",
  stateUnknown: "Status: unavailable (the server did not answer).",
  forcedOn: "Turned on by the BOBINE_MEDIA_NATIVE environment variable: it overrides this setting.",
  forcedOff: "Turned off by the BOBINE_MEDIA_NATIVE environment variable: it overrides this setting.",
  saveError: "The setting could not be saved.",
};
