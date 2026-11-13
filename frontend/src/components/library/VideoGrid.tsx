"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import { formatDuration, programGroups, thumbnailSrc } from "./media";
import type { Selection } from "./selection";
import type { Video } from "./types";

interface Props {
  videos: Video[];
  selection: Selection;
  onOpen: (video: Video) => void;
}

function VideoCard({ video, selected, onToggle, onOpen }: { video: Video; selected: boolean; onToggle: () => void; onOpen: () => void }) {
  const { t } = useAppSettings();
  const thumb = thumbnailSrc(video);
  return (
    <div className={`video-card program-autre${selected ? " selected" : ""}`} onClick={onOpen}>
      <div className="thumbnail-wrapper">
        <input type="checkbox" className="card-select-checkbox" checked={selected} onClick={(e) => e.stopPropagation()} onChange={onToggle} />
        {thumb ? (
          <img src={thumb} alt={video.title} className="card-thumbnail" />
        ) : (
          <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="movie" size={32} style={{ opacity: 0.2 }} />
          </div>
        )}
        <span className="card-duration">{formatDuration(video.duration_seconds)}</span>
      </div>
      <div className="card-content">
        <h4 className="card-title" title={video.title}>{video.title}</h4>
        <div className="card-meta-row">
          <span className="program-badge autre">{video.program || t("library.noProgram")}</span>
          {video.release && <span className="release-badge">{t("library.releaseBadge", { release: video.release })}</span>}
        </div>
      </div>
    </div>
  );
}

export default function VideoGrid({ videos, selection, onOpen }: Props) {
  const { t } = useAppSettings();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
      {programGroups(videos).map((group) => {
        const ids = group.items.map((v) => v.id);
        return (
          <div key={group.program}>
            <h3 style={{ fontSize: "0.85rem", marginBottom: "16px", color: "var(--accent-text)" }}>
              <label style={{ display: "inline-flex", alignItems: "center", gap: "8px", cursor: "pointer" }} title={t("library.selectGroupTitle")}>
                <input
                  type="checkbox"
                  checked={selection.allSelected(ids)}
                  onChange={(e) => selection.setMany(ids, e.target.checked)}
                  style={{ width: "16px", height: "16px", cursor: "pointer" }}
                />
                <span>
                  {group.program === "" ? t("library.noProgram") : group.program}{" "}
                  <span style={{ color: "var(--text-dim)" }}>({group.items.length})</span>
                </span>
              </label>
            </h3>
            <div className="videos-grid">
              {group.items.map((video) => (
                <VideoCard
                  key={video.id}
                  video={video}
                  selected={selection.selectedIds.has(video.id)}
                  onToggle={() => selection.toggle(video.id)}
                  onOpen={() => onOpen(video)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
