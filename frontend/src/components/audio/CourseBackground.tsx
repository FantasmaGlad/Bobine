"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import { thumbnailUrl } from "./media";
import type { BackgroundOption } from "./types";

interface Props {
  selected: BackgroundOption | undefined;
  fallback: BackgroundOption | null;
  chosenId: string;
  onChange: () => void;
}

function Preview({ selected, fallback, chosenId }: Omit<Props, "onChange">) {
  const shown = selected?.thumbnail_path ? selected : !chosenId && fallback?.thumbnail_path ? fallback : null;
  if (shown) {
    return <img src={thumbnailUrl(shown.thumbnail_path)!} alt={shown.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />;
  }
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", opacity: 0.4 }}>
      <Icon name={chosenId ? "image" : "hide_image"} size={20} />
    </div>
  );
}

export default function CourseBackground(props: Props) {
  const { t } = useAppSettings();
  const { selected, fallback } = props;
  const name = selected ? selected.title : fallback ? `${fallback.title} (${t("backgrounds.defaultBadge")})` : t("audio.noBackgroundOption");
  const detail = selected
    ? t(selected.is_image ? "audio.customStillImage" : "audio.customVideoLoop")
    : t(fallback ? "backgrounds.defaultClubAmbiance" : "backgrounds.noBackgroundAmbiance");
  return (
    <div className="form-group">
      <label className="form-label">{t("audio.backgroundAssociationLabel")}</label>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", background: "var(--bg-surface-elevated)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-md)", padding: "8px 12px" }}>
        <div style={{ width: "72px", height: "40.5px", borderRadius: "6px", overflow: "hidden", background: "var(--bg-surface-hover)", position: "relative", flexShrink: 0 }}>
          <Preview {...props} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{detail}</div>
        </div>
        <button type="button" className="btn btn-secondary" style={{ height: "34px", padding: "0 10px", fontSize: "0.8rem", whiteSpace: "nowrap" }} onClick={props.onChange}>
          {t("coach.changeAmbianceBtn")}
        </button>
      </div>
    </div>
  );
}
