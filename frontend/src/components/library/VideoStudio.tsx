"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { ShowToast } from "@/lib/useToast";

import StudioForm from "./StudioForm";
import StudioMedia from "./StudioMedia";
import type { Video } from "./types";
import { useVideoStudio } from "./useVideoStudio";

interface Props {
  video: Video;
  showToast: ShowToast;
  onClose: () => void;
  onUpdated: (video: Video) => void;
  onDelete: (video: Video) => void;
}

export default function VideoStudio({ video, showToast, onClose, onUpdated, onDelete }: Props) {
  const { t } = useAppSettings();
  const studio = useVideoStudio(video, showToast, onUpdated);
  return (
    <div className="course-studio-overlay" onClick={onClose}>
      <div className="course-studio-modal" onClick={(e) => e.stopPropagation()}>
        <div className="course-studio-header">
          <div style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
            <div className="course-studio-icon-badge">
              <Icon name="movie_filter" size={22} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "var(--accent-text)", letterSpacing: "0.08em" }}>
                {t("library.studioTitle")}
              </div>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {studio.fields.title || video.title}
              </h2>
            </div>
          </div>
          <button className="close-btn olc-press" onClick={onClose} aria-label={t("common.close")}>
            <Icon name="close" size={20} />
          </button>
        </div>
        <div className="course-studio-body">
          <StudioMedia video={video} studio={studio} onDelete={() => onDelete(video)} />
          <StudioForm video={video} studio={studio} showToast={showToast} onClose={onClose} />
        </div>
      </div>
    </div>
  );
}
