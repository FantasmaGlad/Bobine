"use client";

import type { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import BackgroundCard from "./BackgroundCard";
import type { BackgroundItem } from "./types";

type PlaybackState = ReturnType<typeof usePlaybackSocket>["state"];

export default function BackgroundGrid({ t, loading, backgrounds, defaultCoachBgId, cableState, networkState, onInspect, onDelete }: {
  t: (key: string) => string;
  loading: boolean;
  backgrounds: BackgroundItem[];
  defaultCoachBgId: number | null;
  cableState: PlaybackState;
  networkState: PlaybackState;
  onInspect: (bg: BackgroundItem) => void;
  onDelete: (bg: BackgroundItem) => void;
}) {
  if (loading) {
    return (
      <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
        {t("backgrounds.loadingBackgrounds")}
      </div>
    );
  }
  if (backgrounds.length === 0) {
    return (
      <div style={{ display: "flex", flex: 1, flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
        <p style={{ margin: 0, fontWeight: 600 }}>{t("backgrounds.noBackgroundsTitle")}</p>
        <p style={{ fontSize: "0.85rem", margin: "4px 0 0" }}>{t("backgrounds.noBackgroundsHint")}</p>
      </div>
    );
  }
  return (
    <div className="videos-grid">
      {backgrounds.map((bg) => (
        <BackgroundCard
          key={bg.id}
          bg={bg}
          isDefault={defaultCoachBgId === bg.id}
          isActiveCable={cableState.state === "background" && cableState.current_background?.id === bg.id}
          isActiveNetwork={networkState.state === "background" && networkState.current_background?.id === bg.id}
          onClick={() => onInspect(bg)}
          onDelete={() => onDelete(bg)}
        />
      ))}
    </div>
  );
}
