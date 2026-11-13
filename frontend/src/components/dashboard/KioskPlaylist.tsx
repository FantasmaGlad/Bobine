"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { PlaybackState } from "@/lib/usePlaybackSocket";

import type { Send } from "./types";

type Item = { title: string } | null | undefined;

const SMALL_BUTTON = { height: "28px", padding: "0 10px", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "4px" } as const;

export function PlaylistBar({ state, sendCommand }: { state: PlaybackState; sendCommand: Send }) {
  const { t } = useAppSettings();
  const items = state.playlist_items;
  const index = state.playlist_index;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "color-mix(in srgb, var(--accent-primary) 3%, transparent)", padding: "10px 12px", borderRadius: "var(--radius-md)", border: "1px solid color-mix(in srgb, var(--accent-primary) 15%, transparent)", marginBottom: "12px" }}>
      <span style={{ fontSize: "0.85rem", color: "var(--accent-text)", fontWeight: 700 }}>
        {t("dashboard.playlistLabel", { name: state.playlist_name ?? "", index: (index ?? 0) + 1, total: items?.length ?? 0 })}
      </span>
      {items && index !== null && (
        <div style={{ display: "flex", gap: "8px" }}>
          <button className="btn btn-secondary" style={SMALL_BUTTON} onClick={() => sendCommand("previous_video")} disabled={index === 0} title={t("dashboard.previousCourse")}>
            <Icon name="skip_previous" size={16} />
            {t("dashboard.previousShort")}
          </button>
          <button className="btn btn-secondary" style={SMALL_BUTTON} onClick={() => sendCommand("next_video")} disabled={index === items.length - 1} title={t("dashboard.nextCourse")}>
            {t("dashboard.nextShort")}
            <Icon name="skip_next" size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

export function PlaylistWaiting({ state, next, sendCommand }: { state: PlaybackState; next: Item; sendCommand: Send }) {
  const { t } = useAppSettings();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px", alignItems: "center", justifyContent: "center", padding: "20px", background: "var(--bg-surface-hover)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-color)" }}>
      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>{t("dashboard.transitionRemaining")}</span>
      <span style={{ fontSize: "2.5rem", fontWeight: 900, color: "var(--accent-text)", fontVariantNumeric: "tabular-nums" }}>{Math.ceil(state.playlist_waiting_remaining ?? 0)} s</span>
      {next ? (
        <span style={{ fontSize: "0.9rem", color: "var(--text-main)", fontWeight: 700, textAlign: "center" }}>{t("dashboard.nextCourseLabel", { title: next.title })}</span>
      ) : (
        <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>{t("dashboard.playlistEnd")}</span>
      )}
      <div style={{ display: "flex", gap: "10px", width: "100%", marginTop: "8px" }}>
        <button className="btn btn-primary" style={{ flex: 1, height: "40px", fontSize: "0.85rem" }} onClick={() => sendCommand("skip_waiting")}>
          <Icon name="fast_forward" size={16} />
          {t("dashboard.launchImmediately")}
        </button>
        <button className="btn btn-secondary" style={{ height: "40px", padding: "0 16px", fontSize: "0.85rem" }} onClick={() => sendCommand("stop")}>
          <Icon name="stop" size={16} />
          {t("dashboard.stop")}
        </button>
      </div>
    </div>
  );
}
