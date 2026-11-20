import { getAcceptedCodecs } from "@/lib/clientCodecSupport";

const CODEC_ROWS: ReadonlyArray<readonly [string, string, string]> = [
  ["H.264 (AVC)", "h264", 'video/mp4; codecs="avc1.640028"'],
  ["H.264 High 10", "hi10", 'video/mp4; codecs="avc1.6E0028"'],
  ["H.265 (HEVC)", "hevc", 'video/mp4; codecs="hvc1.1.6.L93.B0"'],
  ["VP9", "vp9", 'video/mp4; codecs="vp09.00.10.08"'],
  ["AV1", "av1", 'video/mp4; codecs="av01.0.08M.08"'],
  ["AAC", "aac", 'audio/mp4; codecs="mp4a.40.2"'],
  ["MP3", "mp3", "audio/mpeg"],
  ["Opus", "opus", 'audio/webm; codecs="opus"'],
  ["FLAC", "flac", "audio/flac"],
];

export interface FeatureRow {
  label: string;
  supported: boolean;
}

function detectFeatures(): FeatureRow[] {
  const video = document.createElement("video");
  return [
    { label: "WebSocket", supported: "WebSocket" in window },
    { label: "Web Audio (AudioContext)", supported: "AudioContext" in window || "webkitAudioContext" in window },
    { label: "Screen Wake Lock", supported: "wakeLock" in navigator },
    { label: "Gamepad API", supported: "getGamepads" in navigator },
    { label: "Media Session", supported: "mediaSession" in navigator },
    { label: "MediaCapabilities", supported: "mediaCapabilities" in navigator },
    { label: "requestVideoFrameCallback", supported: "requestVideoFrameCallback" in video },
    { label: "Fullscreen API", supported: !!document.documentElement.requestFullscreen },
    { label: "Folder drop (webkitdirectory)", supported: "webkitdirectory" in document.createElement("input") },
  ];
}

export interface Capabilities {
  secure: boolean;
  codecs: Array<{ label: string; support: string }>;
  features: FeatureRow[];
  accept: string;
  cores: number | null;
}

function collect(): Capabilities {
  const video = document.createElement("video");
  const audio = document.createElement("audio");
  return {
    secure: window.isSecureContext,
    codecs: CODEC_ROWS.map(([label, , type]) => ({
      label,
      support: (type.startsWith("audio") ? audio : video).canPlayType(type) || "",
    })),
    features: detectFeatures(),
    accept: getAcceptedCodecs(),
    cores: navigator.hardwareConcurrency || null,
  };
}

let capabilities: Capabilities | null = null;
export const readCapabilities = () => (capabilities ??= collect());

export function compatReport(caps: Capabilities, playback: string | null): string {
  return JSON.stringify(
    {
      secureContext: caps.secure,
      hardwareConcurrency: caps.cores,
      accept: caps.accept,
      codecs: Object.fromEntries(caps.codecs.map((c) => [c.label, c.support || "non"])),
      features: Object.fromEntries(caps.features.map((f) => [f.label, f.supported])),
      playback,
      userAgent: navigator.userAgent,
    },
    null,
    2,
  );
}
