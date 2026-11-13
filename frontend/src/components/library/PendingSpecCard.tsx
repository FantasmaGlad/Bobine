"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { PendingUploadSpec } from "@/lib/UploadManager";

import { PROGRAMS_LIST_ID, SUBTITLE_ACCEPT, type PendingSpec } from "./types";

interface Props {
  spec: PendingSpec;
  onUpdate: (patch: Partial<PendingUploadSpec>) => void;
  onRemove: () => void;
}

function SubtitleChips({ spec, onUpdate }: Omit<Props, "onRemove">) {
  const { t } = useAppSettings();
  if (!spec.subtitles || spec.subtitles.length === 0) {
    return <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontStyle: "italic" }}>{t("common.none")}</span>;
  }
  return (
    <>
      {spec.subtitles.map((subFile, idx) => (
        <span key={idx} className="badge-pill" style={{ display: "inline-flex", alignItems: "center", gap: "4px", background: "color-mix(in srgb, var(--accent-primary) 15%, transparent)", border: "1px solid var(--accent-text)", fontSize: "0.74rem", padding: "2px 8px" }}>
          <Icon name="subtitles" size={12} />
          <span>{subFile.name}</span>
          <button aria-label={t("common.remove")}
            type="button"
            onClick={() => onUpdate({ subtitles: (spec.subtitles ?? []).filter((_, i) => i !== idx) })}
            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0 2px" }}
          >
            <Icon name="close" size={12} />
          </button>
        </span>
      ))}
    </>
  );
}

export default function PendingSpecCard({ spec, onUpdate, onRemove }: Props) {
  const { t } = useAppSettings();
  const file = spec.file!;
  return (
    <div style={{ background: "var(--bg-surface-hover)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "12px 14px", display: "flex", flexDirection: "column", gap: "10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
          <Icon name="movie" size={18} style={{ color: "var(--accent-text)", flexShrink: 0 }} />
          <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={file.name}>
            {file.name}
          </span>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            ({(file.size / (1024 * 1024)).toFixed(1)} Mo)
          </span>
        </div>
        <button onClick={onRemove} className="olc-press" style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", flexShrink: 0, display: "flex", padding: "4px" }} title={t("library.removeFile")}>
          <Icon name="close" size={16} />
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 100px", gap: "8px" }}>
        <input
          type="text"
          className="form-control"
          placeholder={t("library.courseTitlePlaceholder")}
          value={spec.title}
          onChange={(e) => onUpdate({ title: e.target.value })}
          style={{ padding: "6px 10px", fontSize: "0.85rem" }}
        />
        <input
          type="text"
          list={PROGRAMS_LIST_ID}
          className="form-control"
          placeholder={t("library.programPlaceholder")}
          value={spec.program ?? ""}
          onChange={(e) => onUpdate({ program: e.target.value })}
          style={{ padding: "6px 8px", fontSize: "0.85rem" }}
        />
        <input
          type="text"
          className="form-control"
          placeholder={t("library.releasePlaceholderExample")}
          value={spec.release ?? ""}
          onChange={(e) => onUpdate({ release: e.target.value })}
          style={{ padding: "6px 8px", fontSize: "0.85rem" }}
        />
      </div>

      <textarea
        className="form-control"
        placeholder={t("common.descriptionOptional")}
        value={spec.description ?? ""}
        onChange={(e) => onUpdate({ description: e.target.value })}
        rows={2}
        style={{ fontSize: "0.82rem", resize: "vertical", minHeight: "52px", lineHeight: "1.4" }}
      />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px", paddingTop: "6px", borderTop: "1px dashed var(--border-color)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>{t("common.subtitles")}</span>
          <SubtitleChips spec={spec} onUpdate={onUpdate} />
        </div>
        <label className="btn btn-secondary olc-press" style={{ height: "26px", padding: "0 8px", fontSize: "0.74rem", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "4px" }}>
          <Icon name="add" size={14} />
          <span>{t("common.add")} (.srt)</span>
          <input
            type="file"
            accept={SUBTITLE_ACCEPT}
            style={{ display: "none" }}
            onChange={(e) => {
              const picked = e.target.files?.[0];
              if (picked) onUpdate({ subtitles: [...(spec.subtitles ?? []), picked] });
              e.target.value = "";
            }}
          />
        </label>
      </div>
    </div>
  );
}
