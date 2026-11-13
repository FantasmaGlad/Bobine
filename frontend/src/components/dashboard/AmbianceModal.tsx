"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import { thumbnailOf, type BackgroundSummary } from "./types";

interface Props {
  backgrounds: BackgroundSummary[];
  onLaunch: (background: BackgroundSummary) => void;
  onClose: () => void;
}

function Tile({ background, selected, onClick }: { background: BackgroundSummary; selected: boolean; onClick: () => void }) {
  const { t } = useAppSettings();
  const thumb = thumbnailOf(background.thumbnail_path);
  return (
    <div onClick={onClick} className="olc-card-hover olc-press" style={{
      cursor: "pointer", borderRadius: "var(--radius-md)", overflow: "hidden", display: "flex", flexDirection: "column", transition: "all var(--transition-normal)",
      border: selected ? "2px solid var(--accent-text)" : "1px solid var(--border-color)",
      background: selected ? "color-mix(in srgb, var(--accent-primary) 8%, var(--bg-surface))" : "var(--bg-surface)",
    }}>
      <div style={{ position: "relative", width: "100%", aspectRatio: "16/9", background: "var(--bg-surface-elevated)" }}>
        {thumb ? <img src={thumb} alt={background.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : (
          <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="wallpaper" size={24} style={{ opacity: 0.3 }} /></div>
        )}
        <span style={{ position: "absolute", bottom: "6px", right: "6px", background: "color-mix(in srgb, var(--ink) 70%, transparent)", color: "var(--specular)", fontSize: "0.7rem", fontWeight: 700, padding: "2px 6px", borderRadius: "var(--radius-sm)" }}>
          {background.is_image ? t("coach.backgroundImageTag") : t("coach.backgroundVideoTag")}
        </span>
      </div>
      <div style={{ padding: "10px" }}>
        <span style={{ fontSize: "0.85rem", fontWeight: 700, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{background.title}</span>
      </div>
    </div>
  );
}

export default function AmbianceModal({ backgrounds, onLaunch, onClose }: Props) {
  const { t } = useAppSettings();
  const [chosen, setChosen] = useState<BackgroundSummary | null>(null);
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ width: "680px", maxWidth: "94vw", maxHeight: "85vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h3 style={{ margin: "0 0 4px", fontSize: "1.2rem", fontWeight: 800 }}>{t("dashboard.chooseAmbiance")}</h3>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>{t("dashboard.chooseAmbianceHint")}</p>
          </div>
          <button type="button" className="close-btn" onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)" }}><Icon name="close" size={20} /></button>
        </div>
        {backgrounds.length === 0 ? (
          <p className="live-empty" style={{ margin: "24px 0" }}>{t("backgrounds.noBackgrounds")}</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "12px", margin: "16px 0" }}>
            {backgrounds.map((bg) => <Tile key={bg.id} background={bg} selected={chosen?.id === bg.id} onClick={() => setChosen(bg)} />)}
          </div>
        )}
        <div className="modal-actions" style={{ marginTop: "12px", borderTop: "1px solid var(--border-color)", paddingTop: "12px" }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>{t("common.cancel")}</button>
          <button type="button" className="btn btn-primary" disabled={!chosen} onClick={() => chosen && onLaunch(chosen)}>
            <Icon name="play_arrow" size={16} filled />
            {t("dashboard.confirmLaunchAmbiance")}
          </button>
        </div>
      </div>
    </div>
  );
}
