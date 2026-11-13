"use client";

import ChapterEditor from "@/components/ChapterEditor";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

import StudioSubtitles from "./StudioSubtitles";
import { PROGRAMS_LIST_ID, type Video } from "./types";
import type { VideoStudioState } from "./useVideoStudio";

interface Props {
  video: Video;
  studio: VideoStudioState;
  showToast: ShowToast;
  onClose: () => void;
}

const currentTime = () => document.querySelector<HTMLVideoElement>(".course-studio-modal .drawer-video")?.currentTime ?? 0;

function MetadataFields({ studio }: { studio: VideoStudioState }) {
  const { t } = useAppSettings();
  const { fields, setters } = studio;
  return (
    <>
      <div className="form-group">
        <label className="form-label">{t("library.courseTitleFieldLabel")}</label>
        <input
          type="text"
          className="form-control"
          value={fields.title}
          onChange={(e) => setters.setTitle(e.target.value)}
          required
          placeholder={t("common.titleExample")}
          style={{ fontSize: "0.95rem", fontWeight: 600, padding: "10px 14px" }}
        />
      </div>
      <div style={{ display: "flex", gap: "12px" }}>
        <div className="form-group" style={{ flex: 1, minWidth: 0 }}>
          <label className="form-label">{t("library.programLabel")}</label>
          <input type="text" list={PROGRAMS_LIST_ID} className="form-control" value={fields.program} onChange={(e) => setters.setProgram(e.target.value)} placeholder={t("library.programPlaceholder")} />
        </div>
        <div className="form-group" style={{ width: "130px", minWidth: 0 }}>
          <label className="form-label">{t("library.releaseLabel")}</label>
          <input type="text" className="form-control" value={fields.release} onChange={(e) => setters.setRelease(e.target.value)} placeholder={t("library.releasePlaceholderExample")} />
        </div>
      </div>
      <div className="form-group" style={{ flex: "1 1 auto", minHeight: "120px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <label className="form-label">{t("library.descriptionFieldLabel")}</label>
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{t("library.subtitleStyleNote")}</span>
        </div>
        <textarea
          className="form-control"
          value={fields.description}
          onChange={(e) => setters.setDescription(e.target.value)}
          placeholder={t("library.descriptionPlaceholder")}
          style={{ resize: "vertical", minHeight: "110px", maxHeight: "200px", lineHeight: "1.5", fontSize: "0.88rem" }}
        />
      </div>
    </>
  );
}

export default function StudioForm({ video, studio, showToast, onClose }: Props) {
  const { t } = useAppSettings();
  return (
    <div className="course-studio-col-right">
      <form onSubmit={studio.save} style={{ display: "flex", flexDirection: "column", gap: "14px", height: "100%" }}>
        <MetadataFields studio={studio} />
        <StudioSubtitles studio={studio} />
        <ChapterEditor key={video.id} videoId={video.id} getApiUrl={getApiUrl} getCurrentTime={currentTime} onNotify={(message, type) => showToast(message, type)} />
        <div style={{ display: "flex", gap: "10px", marginTop: "auto", paddingTop: "8px" }}>
          <button type="button" className="btn btn-secondary olc-press" onClick={onClose} style={{ height: "44px", padding: "0 18px", fontSize: "0.88rem" }}>
            {t("common.close")}
          </button>
          <button type="submit" className="btn btn-primary olc-press" style={{ flex: 1, height: "44px", fontSize: "0.88rem" }} disabled={studio.saving}>
            <Icon name="save" size={18} />
            <span>{studio.saving ? t("common.saving") : t("common.save")}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
