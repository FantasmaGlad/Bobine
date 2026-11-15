import type { RadioAnnouncementInfo } from "@/lib/useRadioSocket";

export type ActiveAnnouncement = Pick<RadioAnnouncementInfo, "id" | "mode">;

export interface DuckSettings {
  level: number;
  fadeMs: number;
}

export type AnnouncementPlan =
  | { kind: "none" }
  | { kind: "start"; abortCrossfade: true; announcementGain: [number, number]; musicRamp: number | null; fadeMs: number }
  | { kind: "end"; announcementGain: [null, number]; musicRamp: number | null; unloadAfterMs: number };

export function planAnnouncement(
  prev: ActiveAnnouncement | null,
  next: ActiveAnnouncement | null,
  volume: number,
  duck: DuckSettings,
): AnnouncementPlan {
  if (next && next.id !== prev?.id) {
    return {
      kind: "start",
      abortCrossfade: true,
      announcementGain: [0, 1],
      musicRamp: next.mode === "duck" ? duck.level / 100 : null,
      fadeMs: duck.fadeMs,
    };
  }
  if (!next && prev) {
    return {
      kind: "end",
      announcementGain: [null, 0],
      musicRamp: prev.mode === "duck" ? volume / 100 : null,
      unloadAfterMs: duck.fadeMs,
    };
  }
  return { kind: "none" };
}
