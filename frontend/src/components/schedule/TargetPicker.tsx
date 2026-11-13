"use client";

import React, { useMemo } from "react";

import Highlight from "@/components/Highlight";
import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMinutes } from "@/lib/format";
import { matchesQuery } from "@/lib/searchText";
import type { RadioPlaylistSummary } from "@/lib/scheduleTime";

import { coverSrc } from "./media";
import type { ScheduleCatalog } from "./useScheduleData";
import type { ScheduleFormState } from "./useScheduleForm";

interface Props {
  radio: boolean;
  catalog: ScheduleCatalog;
  state: ScheduleFormState;
}

const selectedStyle = (selected: boolean): React.CSSProperties => ({
  cursor: "pointer",
  borderColor: selected ? "var(--accent-text)" : undefined,
  background: selected ? "color-mix(in srgb, var(--accent-primary) 8%, transparent)" : undefined,
});

function RadioOption({ playlist, label, query, selected, onSelect }: { playlist: RadioPlaylistSummary; label: string; query: string; selected: boolean; onSelect: () => void }) {
  const { t } = useAppSettings();
  const cover = coverSrc(playlist.cover_track_id);
  return (
    <div
      className="library-picker-item"
      role="option"
      aria-selected={selected}
      tabIndex={0}
      style={{ ...selectedStyle(selected), display: "flex", alignItems: "center", gap: "10px" }}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      {cover ? (
        <img src={cover} alt="" style={{ width: 44, height: 44, borderRadius: 6, objectFit: "cover", flexShrink: 0 }} />
      ) : (
        <span style={{ width: 44, height: 44, borderRadius: 6, flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center", background: "var(--bg-surface-elevated)" }}>
          <Icon name="queue_music" size={20} style={{ opacity: 0.4 }} />
        </span>
      )}
      <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          <Highlight text={label} query={query} />
        </span>
        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
          {t("schedule.tracksCount", { count: playlist.item_count })} · {formatMinutes(playlist.total_duration_seconds)}
        </span>
      </span>
      {selected && <Icon name="check" size={18} />}
    </div>
  );
}

function selectedName(state: ScheduleFormState, catalog: ScheduleCatalog): string | undefined {
  const id = Number(state.form.targetId);
  if (state.form.targetType === "video") return catalog.videos.find((v) => v.id === id)?.title;
  if (state.form.targetType === "radio_playlist") return catalog.radioPlaylists.find((p) => p.id === id)?.name;
  return catalog.playlists.find((p) => p.id === id)?.name;
}

export default function TargetPicker({ radio, catalog, state }: Props) {
  const { t } = useAppSettings();
  const { form, patch } = state;
  const options = useMemo(
    () =>
      form.targetType === "video"
        ? catalog.videos.map((v) => ({ id: v.id, label: v.title }))
        : form.targetType === "radio_playlist"
        ? catalog.radioPlaylists.map((p) => ({ id: p.id, label: p.name }))
        : catalog.playlists.map((p) => ({ id: p.id, label: p.name })),
    [form.targetType, catalog]
  );
  return (
    <div className="form-group">
      <SearchBox className="form-control" placeholder={t("schedule.searchPlaceholder")} value={form.targetSearch} onChange={(targetSearch) => patch({ targetSearch })} suggestions={options.map((o) => o.label)} />
      <div className="library-picker-list" style={{ maxHeight: radio ? "260px" : "160px" }}>
        {options.filter((o) => matchesQuery(o.label, form.targetSearch)).map((o) => {
          const selected = String(o.id) === form.targetId;
          const select = () => patch({ targetId: String(o.id) });
          const playlist = radio ? catalog.radioPlaylists.find((p) => p.id === o.id) : undefined;
          if (playlist) return <RadioOption key={o.id} playlist={playlist} label={o.label} query={form.targetSearch} selected={selected} onSelect={select} />;
          return (
            <div key={o.id} className="library-picker-item" style={selectedStyle(selected)} onClick={select}>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-main)" }}>{o.label}</span>
            </div>
          );
        })}
      </div>
      {form.targetId && (
        <span style={{ fontSize: "0.75rem", color: "var(--accent-success-text)" }}>
          {t("schedule.selectedLabel")} {selectedName(state, catalog)}
        </span>
      )}
    </div>
  );
}
