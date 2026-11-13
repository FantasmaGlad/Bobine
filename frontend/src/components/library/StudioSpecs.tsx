"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatBitrate, formatFps, getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";

import type { Video } from "./types";

export default function StudioSpecs({ video }: { video: Video }) {
  const { t } = useAppSettings();
  const badge = getResolutionBadge(video.width, video.height);
  return (
    <div className="course-studio-specs-grid">
      <div className="course-studio-spec-item">
        <span className="spec-label">{t("library.resolutionLabel")}</span>
        <span className="spec-val">
          {video.width && video.height ? `${video.width}x${video.height}` : t("library.unknownValue")}
          {badge ? ` (${badge})` : ""}
        </span>
      </div>
      <div className="course-studio-spec-item">
        <span className="spec-label">{t("library.audioQualityLabel")}</span>
        <span className="spec-val">{getAudioQualityBadge(video.audio_channels, video.audio_codec, undefined, t)}</span>
      </div>
      <div className="course-studio-spec-item">
        <span className="spec-label">{t("library.framerateLabel")} / Codec</span>
        <span className="spec-val">{video.fps ? formatFps(video.fps) : "--"} • {video.codec || "H264"}</span>
      </div>
      <div className="course-studio-spec-item">
        <span className="spec-label">{t("library.bitrateLabel")}</span>
        <span className="spec-val">{video.bitrate_kbps ? formatBitrate(video.bitrate_kbps) : "--"}</span>
      </div>
      <div className="course-studio-spec-item" style={{ gridColumn: "span 2" }}>
        <span className="spec-label">{t("library.diskLocation")}</span>
        <span className="spec-val" style={{ fontSize: "0.74rem", opacity: 0.8, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={video.file_path}>
          {video.file_path}
        </span>
      </div>
    </div>
  );
}
