export type VideoProfilePreference = "auto" | "web" | "original";

const PROFILE_STORAGE_KEY = "bobine.videoProfile";

const PROBES: ReadonlyArray<readonly [string, string]> = [
  ["h264", 'video/mp4; codecs="avc1.640028"'],
  ["hevc", 'video/mp4; codecs="hvc1.1.6.L93.B0"'],
  ["vp9", 'video/mp4; codecs="vp09.00.10.08"'],
  ["av1", 'video/mp4; codecs="av01.0.08M.08"'],
  ["hi10", 'video/mp4; codecs="avc1.6E0028"'],
];

let cachedAccept: string | null = null;

export function getAcceptedCodecs(): string {
  if (cachedAccept !== null) return cachedAccept;
  if (typeof document === "undefined") return "";
  try {
    const probe = document.createElement("video");
    cachedAccept = PROBES.filter(([, type]) => probe.canPlayType(type) !== "").map(([name]) => name).join(",");
  } catch {
    cachedAccept = "";
  }
  return cachedAccept;
}

export function getVideoProfilePreference(): VideoProfilePreference {
  try {
    const value = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    return value === "web" || value === "original" ? value : "auto";
  } catch {
    return "auto";
  }
}

export function setVideoProfilePreference(value: VideoProfilePreference): void {
  try {
    if (value === "auto") window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    else window.localStorage.setItem(PROFILE_STORAGE_KEY, value);
  } catch {
  }
}

export function videoStreamQuery(): string {
  if (typeof window === "undefined") return "";
  const preference = getVideoProfilePreference();
  const params = new URLSearchParams();
  const accept = getAcceptedCodecs();
  if (accept) params.set("accept", accept);
  if (preference !== "auto") params.set("profile", preference);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function videoStreamUrl(apiUrl: (path: string) => string, videoId: number | string): string {
  return `${apiUrl(`/videos/${videoId}/stream`)}${videoStreamQuery()}`;
}
