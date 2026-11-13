"use client";

import React from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import { thumbnailUrl } from "./media";
import type { BackgroundOption } from "./types";

interface Props {
  forTrack: boolean;
  backgrounds: BackgroundOption[];
  defaultBackground: BackgroundOption | null;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  onClose: () => void;
}

function OptionRow({ active, thumb, title, detail, onClick, last }: { active: boolean; thumb: React.ReactNode; title: React.ReactNode; detail: string; onClick: () => void; last?: boolean }) {
  return (
    <div
      className={`olc-press ${active ? "active" : ""}`}
      style={{
        display: "flex", alignItems: "center", gap: "12px", padding: "10px 12px", borderRadius: "8px", cursor: "pointer", marginBottom: last ? "14px" : "10px",
        background: active ? "var(--bg-surface-hover)" : "var(--bg-surface-elevated)",
        border: `1.5px solid ${active ? "var(--accent-text)" : "var(--border-color)"}`,
      }}
      onClick={onClick}
    >
      <div style={{ width: "64px", height: "36px", borderRadius: "4px", overflow: "hidden", background: "var(--bg-surface-hover)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{thumb}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: "0.88rem", display: "flex", alignItems: "center", gap: "6px" }}>{title}</div>
        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{detail}</div>
      </div>
      {active && <Icon name="check_circle" size={20} color="var(--accent-text)" filled />}
    </div>
  );
}

function FixedOptions({ forTrack, defaultBackground, selectedId, onSelect }: Omit<Props, "backgrounds" | "onClose">) {
  const { t } = useAppSettings();
  if (forTrack) {
    return <OptionRow last active={selectedId === null} thumb={<Icon name="auto_awesome" size={20} color="var(--accent-text)" />} title={t("audio.courseAmbianceDefault")} detail={t("audio.courseAmbianceKeep")} onClick={() => onSelect(null)} />;
  }
  const defaultThumb = thumbnailUrl(defaultBackground?.thumbnail_path);
  return (
    <>
      {defaultBackground && (
        <OptionRow
          active={selectedId === null}
          thumb={defaultThumb
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={defaultThumb} alt={defaultBackground.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            : <Icon name="bookmark" size={18} color="var(--accent-text)" />}
          title={<><span>{defaultBackground.title}</span><span style={{ fontSize: "0.72rem", background: "var(--accent-primary)", color: "var(--accent-primary-fg)", padding: "2px 6px", borderRadius: "4px" }}>{t("backgrounds.defaultBadge")}</span></>}
          detail={t("backgrounds.defaultClubAmbiance")}
          onClick={() => onSelect(null)}
        />
      )}
      <OptionRow last active={!defaultBackground && selectedId === null} thumb={<Icon name="hide_image" size={20} style={{ opacity: 0.5 }} />} title={t("backgrounds.noBackgroundAmbiance")} detail={t("audio.plainScreen")} onClick={() => onSelect(null)} />
    </>
  );
}

function BackgroundTile({ background, selected, onClick }: { background: BackgroundOption; selected: boolean; onClick: () => void }) {
  const thumb = thumbnailUrl(background.thumbnail_path);
  return (
    <div className="olc-press" onClick={onClick} style={{ background: selected ? "var(--bg-surface-hover)" : "var(--bg-surface-elevated)", border: `2px solid ${selected ? "var(--accent-text)" : "var(--border-color)"}`, borderRadius: "8px", overflow: "hidden", cursor: "pointer", display: "flex", flexDirection: "column" }}>
      <div style={{ width: "100%", aspectRatio: "16/9", background: "var(--bg-surface-hover)", position: "relative" }}>
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={background.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name={background.is_image ? "image" : "videocam"} size={22} style={{ opacity: 0.4 }} />
          </div>
        )}
        {selected && (
          <div style={{ position: "absolute", top: 4, right: 4, background: "var(--accent-primary)", borderRadius: "50%", width: "20px", height: "20px", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="check" size={14} color="var(--accent-primary-fg)" />
          </div>
        )}
      </div>
      <div style={{ padding: "6px 8px", fontSize: "0.78rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={background.title}>{background.title}</div>
    </div>
  );
}

export default function BackgroundPicker(props: Props) {
  const { t } = useAppSettings();
  const { forTrack, backgrounds, selectedId, onSelect, onClose } = props;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "620px", width: "100%", maxHeight: "85vh", display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 800 }}>{forTrack ? t("audio.trackAmbianceTitle") : t("dashboard.chooseAmbiance")}</h3>
            {forTrack && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{t("audio.ambianceAutoStart")}</span>}
          </div>
          <button className="coach-icon-btn olc-press" style={{ width: "36px", height: "36px", fontSize: "0.9rem" }} onClick={onClose}><Icon name="close" size={18} /></button>
        </div>
        <div style={{ overflowY: "auto", flex: 1, paddingRight: "4px" }}>
          <FixedOptions {...props} />
          <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
            {t("backgrounds.hubTitle")} ({backgrounds.length})
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: "10px" }}>
            {backgrounds.map((bg) => <BackgroundTile key={bg.id} background={bg} selected={selectedId === bg.id} onClick={() => onSelect(bg.id)} />)}
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "16px" }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>{t("common.close")}</button>
        </div>
      </div>
    </div>
  );
}
