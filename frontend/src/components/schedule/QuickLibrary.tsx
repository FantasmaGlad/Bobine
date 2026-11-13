"use client";

import React, { useState } from "react";

import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMinutes } from "@/lib/format";
import { matchesQuery } from "@/lib/searchText";
import type { TargetType } from "@/lib/scheduleTime";

import { blockMinutes, coverSrc, thumbnailSrc } from "./media";
import PickerCard from "./PickerCard";
import type { ScheduleDrag } from "./useDrag";
import type { ScheduleCatalog } from "./useScheduleData";

interface Props {
  radio: boolean;
  catalog: ScheduleCatalog;
  drag: ScheduleDrag;
  isMobile: boolean;
  onClose: () => void;
  onPick: (preset: { type: TargetType; id: number }) => void;
}

const EMPTY = { gridColumn: "1 / -1", textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem", padding: "12px" } as const;
const BADGE = { fontSize: "0.55rem", padding: "1px 4px" } as const;

function RadioCards({ catalog, drag, isMobile, onPick, query }: Omit<Props, "radio" | "onClose"> & { query: string }) {
  const { t } = useAppSettings();
  const shown = catalog.radioPlaylists.filter((p) => matchesQuery(p.name, query));
  return (
    <>
      {shown.map((p) => (
        <PickerCard
          key={`rp-${p.id}`}
          payload={{ type: "radio_playlist", id: p.id, durationMinutes: blockMinutes(p.total_duration_seconds), label: p.name }}
          thumb={coverSrc(p.cover_track_id)}
          fallbackIcon="queue_music"
          duration={formatMinutes(p.total_duration_seconds)}
          title={<><Icon name={p.is_default ? "star" : "queue_music"} size={12} /> {p.name}</>}
          meta={<span className="release-badge" style={BADGE}>{t("schedule.tracksCount", { count: p.item_count })}</span>}
          isMobile={isMobile}
          drag={drag}
          onPick={() => onPick({ type: "radio_playlist", id: p.id })}
        />
      ))}
      {catalog.radioPlaylists.length === 0 && <div style={EMPTY}>{t("schedule.noRadioPlaylists")}</div>}
      {catalog.radioPlaylists.length > 0 && shown.length === 0 && <div style={EMPTY}>{t("schedule.noResults")}</div>}
    </>
  );
}

function VideoCards({ catalog, drag, isMobile, query }: Omit<Props, "radio" | "onClose" | "onPick"> & { query: string }) {
  const { t } = useAppSettings();
  const videos = catalog.videos.filter((v) => matchesQuery(v.title, query));
  const playlists = catalog.playlists.filter((p) => matchesQuery(p.name, query));
  return (
    <>
      {videos.map((v) => (
        <PickerCard
          key={`v-${v.id}`}
          payload={{ type: "video", id: v.id, durationMinutes: blockMinutes(v.duration_seconds), label: v.title }}
          thumb={thumbnailSrc(v.thumbnail_path)}
          fallbackIcon="movie"
          duration={formatMinutes(v.duration_seconds)}
          title={v.title}
          meta={v.program ? <span className="program-badge autre" style={BADGE}>{v.program}</span> : undefined}
          isMobile={isMobile}
          drag={drag}
        />
      ))}
      {playlists.map((p) => (
        <PickerCard
          key={`p-${p.id}`}
          payload={{ type: "playlist", id: p.id, durationMinutes: blockMinutes(p.total_duration_seconds), label: p.name }}
          thumb={thumbnailSrc(p.thumbnail_path)}
          fallbackIcon="playlist_play"
          duration={formatMinutes(p.total_duration_seconds)}
          title={<><Icon name="playlist_play" size={12} /> {p.name}</>}
          meta={<span className="release-badge" style={BADGE}>{t("schedule.coursesCount", { count: p.item_count })}</span>}
          isMobile={isMobile}
          drag={drag}
        />
      ))}
      {videos.length === 0 && playlists.length === 0 && <div style={EMPTY}>{t("schedule.noResults")}</div>}
    </>
  );
}

export default function QuickLibrary(props: Props) {
  const { t } = useAppSettings();
  const [query, setQuery] = useState("");
  const { radio, catalog, isMobile, onClose } = props;
  const suggestions = radio ? catalog.radioPlaylists.map((p) => p.name) : [...catalog.videos.map((v) => v.title), ...catalog.playlists.map((p) => p.name)];
  return (
    <div className="library-picker glass-floating" style={{ width: isMobile ? "100%" : "260px", height: "auto", flexShrink: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="form-label" style={{ margin: 0 }}>{t(radio ? "schedule.radioQuickLibrary" : "schedule.quickLibrary")}</span>
        <button className="close-btn" onClick={onClose} title={t("schedule.hide")}>
          <Icon name="close" size={16} />
        </button>
      </div>
      <SearchBox className="form-control" placeholder={t("schedule.searchPlaceholder")} value={query} onChange={setQuery} suggestions={suggestions} style={{ height: "32px", fontSize: "0.8rem" }} />
      <p style={{ fontSize: "0.7rem", color: "var(--text-dim)", margin: 0 }}>{t(radio ? "schedule.radioDragHint" : "schedule.dragHint")}</p>
      <div className="library-picker-list">
        {radio ? <RadioCards {...props} query={query} /> : <VideoCards {...props} query={query} />}
      </div>
    </div>
  );
}
