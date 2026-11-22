export interface SeekHud {
  position: number;
  duration: number;
}

export type OsdContent = { icon: string; label: string } | null;

export type KioskFeedback = { seekHud: SeekHud } | { osd: NonNullable<OsdContent> } | null;

interface FeedbackData {
  position_seconds?: number | null;
  speed?: number | null;
  current_video?: { duration_seconds?: number | null } | null;
}

export function kioskFeedback(cause: string, data: FeedbackData): KioskFeedback {
  if (cause === "seek") {
    return { seekHud: { position: data.position_seconds ?? 0, duration: data.current_video?.duration_seconds ?? 0 } };
  }
  if (cause === "speed" && typeof data.speed === "number") {
    return { osd: { icon: "speed", label: `${data.speed.toFixed(2)}x` } };
  }
  return null;
}
