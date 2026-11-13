"use client";

import { useRef } from "react";

import Icon from "@/components/Icon";
import WebRenditionPanel from "@/components/WebRenditionPanel";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { videoStreamUrl } from "@/lib/clientCodecSupport";
import { subtitleSrc } from "@/lib/subtitles";

import { thumbnailSrc } from "./media";
import StudioSpecs from "./StudioSpecs";
import type { Video } from "./types";
import type { VideoStudioState } from "./useVideoStudio";

interface Props {
  video: Video;
  studio: VideoStudioState;
  onDelete: () => void;
}

function ThumbnailRow({ video, studio }: Omit<Props, "onDelete">) {
  const { t } = useAppSettings();
  const input = useRef<HTMLInputElement>(null);
  const thumb = thumbnailSrc(video);
  return (
    <div className="course-studio-thumb-row">
      <div className="course-studio-thumb-preview">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <Icon name="movie" size={24} style={{ opacity: 0.3 }} />
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "4px" }}>
        <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
          {t("library.thumbnailFieldLabel")}
        </span>
        <button
          type="button"
          className="btn btn-secondary olc-press"
          style={{ height: "36px", fontSize: "0.82rem", alignSelf: "flex-start" }}
          onClick={() => input.current?.click()}
          disabled={studio.uploadingThumbnail}
        >
          <Icon name="image" size={16} />
          <span>{studio.uploadingThumbnail ? t("common.saving") : t("library.changeThumbnail")}</span>
        </button>
        <input
          ref={input}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) studio.uploadThumbnail(file);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}

export default function StudioMedia({ video, studio, onDelete }: Props) {
  const { t } = useAppSettings();
  return (
    <div className="course-studio-col-left">
      <div className="drawer-video-container" style={{ borderRadius: "12px", overflow: "hidden" }}>
        <video
          key={video.id}
          className="drawer-video"
          controls
          playsInline
          preload="metadata"
          crossOrigin="anonymous"
          src={videoStreamUrl(getApiUrl, video.id)}
          poster={thumbnailSrc(video) || undefined}
        >
          {studio.subtitles.map((sub, i) => (
            <track key={sub.id} kind="subtitles" src={subtitleSrc(getApiUrl, sub.vtt_url)} srcLang={sub.language_code} label={sub.language_label} default={i === 0} />
          ))}
        </video>
        <WebRenditionPanel key={video.id} videoId={video.id} />
      </div>
      <ThumbnailRow video={video} studio={studio} />
      <StudioSpecs video={video} />
      <div style={{ display: "flex", gap: "10px", marginTop: "auto" }}>
        <button type="button" className="btn btn-secondary olc-press" onClick={studio.normalize} style={{ flex: 1, height: "40px", fontSize: "0.82rem" }} title={t("library.normalizeTitle")}>
          <Icon name="tune" size={16} />
          <span>{t("library.normalize")}</span>
        </button>
        <button type="button" className="btn btn-danger olc-press" onClick={onDelete} style={{ height: "40px", fontSize: "0.82rem", padding: "0 14px" }}>
          <Icon name="delete" size={16} />
          <span>{t("common.delete")}</span>
        </button>
      </div>
    </div>
  );
}
