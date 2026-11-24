export function createPlaybackAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  try {
    return new Ctor({ latencyHint: "playback" });
  } catch {
    try {
      return new Ctor();
    } catch {
      return null;
    }
  }
}
