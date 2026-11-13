"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import { formatDuration, thumbnailSrc } from "./media";
import type { Selection } from "./selection";
import type { Video } from "./types";

interface Props {
  videos: Video[];
  selection: Selection;
  onOpen: (video: Video) => void;
}

const CHECKBOX = { width: "18px", height: "18px", cursor: "pointer" } as const;

function Thumb({ video }: { video: Video }) {
  const thumb = thumbnailSrc(video);
  if (thumb) return <img src={thumb} alt="" className="table-thumb" />;
  return (
    <div className="table-thumb" style={{ background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Icon name="movie" size={16} style={{ opacity: 0.2 }} />
    </div>
  );
}

export default function VideoTable({ videos, selection, onOpen }: Props) {
  const { t } = useAppSettings();
  const ids = videos.map((v) => v.id);
  return (
    <div className="table-wrapper">
      <table className="videos-table responsive-table responsive-table--library">
        <thead>
          <tr>
            <th style={{ width: "36px" }}>
              <input type="checkbox" checked={selection.allSelected(ids)} onChange={(e) => selection.setMany(ids, e.target.checked)} title={t("library.selectAllTitle")} style={CHECKBOX} />
            </th>
            <th style={{ width: "80px" }}>{t("library.thumbnailHeader")}</th>
            <th>{t("library.titleHeader")}</th>
            <th>{t("library.programHeader")}</th>
            <th>{t("library.releaseHeader")}</th>
            <th>{t("library.durationHeader")}</th>
            <th>{t("library.formatHeader")}</th>
          </tr>
        </thead>
        <tbody>
          {videos.map((video, index) => (
            <tr key={video.id} className={selection.selectedIds.has(video.id) ? "row-selected" : ""} onClick={() => onOpen(video)}>
              <td onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={selection.selectedIds.has(video.id)}
                  onChange={() => {}}
                  onClick={(e) => selection.rangeClick(e, index, video.id)}
                  title={t("library.selectAllTitle")}
                  style={CHECKBOX}
                />
              </td>
              <td><Thumb video={video} /></td>
              <td style={{ fontWeight: 700, color: "var(--text-main)" }}>{video.title}</td>
              <td><span className="program-badge autre">{video.program || t("library.noProgram")}</span></td>
              <td>{video.release ? t("library.releaseFull", { release: video.release }) : "-"}</td>
              <td>{formatDuration(video.duration_seconds)}</td>
              <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                {video.width && video.height ? `${video.width}x${video.height}` : ""} {video.codec ? `(${video.codec})` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
