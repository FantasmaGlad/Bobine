"use client";

import { useRef } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import { SUBTITLE_ACCEPT } from "./types";
import type { VideoStudioState } from "./useVideoStudio";

function SubtitleTags({ studio }: { studio: VideoStudioState }) {
  const { t } = useAppSettings();
  if (studio.subtitles.length === 0) {
    return (
      <div style={{ padding: "12px", textAlign: "center", background: "color-mix(in srgb, var(--ink) 15%, transparent)", borderRadius: "8px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
        {t("library.noSubtitles")}
      </div>
    );
  }
  return (
    <div className="course-studio-subtitles-list">
      {studio.subtitles.map((sub) => (
        <div key={sub.id} className="course-studio-subtitle-tag">
          <span style={{ fontWeight: 800, textTransform: "uppercase", fontSize: "0.72rem", background: "var(--accent-primary)", color: "var(--accent-primary-fg)", padding: "1px 5px", borderRadius: "4px" }}>
            {sub.language_code}
          </span>
          <span>{sub.language_label}</span>
          <button
            type="button"
            onClick={() => studio.deleteSubtitle(sub.id)}
            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0 2px", display: "flex", alignItems: "center" }}
            title={t("library.deleteSubtitle")}
          >
            <Icon name="close" size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

export default function StudioSubtitles({ studio }: { studio: VideoStudioState }) {
  const { t } = useAppSettings();
  const input = useRef<HTMLInputElement>(null);
  const count = studio.subtitles.length;
  return (
    <div className="course-studio-subtitles-section">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Icon name="subtitles" size={18} style={{ color: "var(--accent-text)" }} />
          <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em" }}>{t("library.syncedSubtitles")}</span>
          <span className="badge-pill" style={{ background: "color-mix(in srgb, var(--specular) 8%, transparent)", fontSize: "0.72rem", padding: "2px 6px" }}>
            {t(count > 1 ? "library.tracksMany" : "library.tracksOne", { count })}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <input
            ref={input}
            type="file"
            accept={SUBTITLE_ACCEPT}
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) studio.uploadSubtitle(file);
              e.target.value = "";
            }}
          />
          <button type="button" className="btn btn-secondary olc-press" style={{ height: "30px", padding: "0 10px", fontSize: "0.78rem" }} onClick={() => input.current?.click()}>
            <Icon name="add" size={14} />
            <span>Ajouter (.srt, .vtt)</span>
          </button>
        </div>
      </div>
      <SubtitleTags studio={studio} />
    </div>
  );
}
