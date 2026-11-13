"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";

import { AddableTracks, PlaylistItems } from "./PlaylistTracks";
import type { PlaylistDetail, RadioOutput, RadioTrack } from "./types";
import type { PlaylistEditor } from "./usePlaylistEditor";

interface Props {
  editor: PlaylistEditor;
  playlist: PlaylistDetail;
  tracks: RadioTrack[];
  suggestions: string[];
  coverUrl: (id: number) => string;
}

const OUTPUTS: RadioOutput[] = ["radio_cable", "radio_network"];

function Meta({ editor, playlist }: Pick<Props, "editor" | "playlist">) {
  const { t } = useAppSettings();
  const askDelete = () => editor.setToDelete({
    id: playlist.id, name: playlist.name, is_default: playlist.is_default, item_count: playlist.items.length,
    total_duration_seconds: playlist.total_duration_seconds, cover_track_id: null,
  });
  return (
    <div className="rl-pl-meta">
      <span>{t("radioLibrary.itemsInPlaylist", { count: playlist.items.length })}</span>
      <span className="rl-pl-meta-dot">·</span>
      <span>{formatMediaDuration(playlist.total_duration_seconds)}</span>
      <div className="rl-toolbar-spacer" />
      <button type="button" className={`rl-pl-star ${playlist.is_default ? "on" : ""}`} onClick={editor.toggleDefault} title={playlist.is_default ? t("radioLibrary.unsetDefault") : t("radioLibrary.setDefault")}>
        <Icon name="star" size={18} filled={playlist.is_default} />
      </button>
      <button type="button" className="rl-pl-star" onClick={askDelete} title={t("radioLibrary.deletePlaylist")}>
        <Icon name="delete" size={18} />
      </button>
    </div>
  );
}

function Outputs({ editor, playlist }: Pick<Props, "editor" | "playlist">) {
  const { t } = useAppSettings();
  return (
    <div className="rl-pl-outputs" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", padding: "0 16px 10px" }}>
      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }} title={t("radioLibrary.outputDefaultHint")}>{t("radioLibrary.outputDefaultLabel")}</span>
      {OUTPUTS.map((output) => {
        const chosen = editor.outputDefaults?.[output]?.override_playlist_id === playlist.id;
        return (
          <button key={output} type="button" className={`btn ${chosen ? "btn-primary" : "btn-secondary"}`} style={{ height: "30px", padding: "0 12px", fontSize: "0.78rem" }}
            aria-pressed={chosen} title={t("radioLibrary.outputDefaultHint")} onClick={() => editor.toggleOutput(output)}>
            <Icon name={output === "radio_cable" ? "cable" : "wifi"} size={14} />
            {output === "radio_cable" ? t("radioLibrary.outputCable") : t("radioLibrary.outputNetwork")}
          </button>
        );
      })}
    </div>
  );
}

export default function PlaylistDrawer({ editor, playlist, tracks, suggestions, coverUrl }: Props) {
  const { t } = useAppSettings();
  const [query, setQuery] = useState("");
  return (
    <>
      <div className="detail-drawer-overlay" onClick={editor.close} />
      <div className="detail-drawer rl-pl-drawer">
        <div className="drawer-header rl-pl-header">
          <input type="text" className="rl-pl-name-input" value={playlist.name}
            onChange={(e) => editor.setPlaylist({ ...playlist, name: e.target.value })}
            onBlur={(e) => editor.rename(e.target.value.trim() || playlist.name)}
            aria-label={t("radioLibrary.playlistNameLabel")} />
          <button aria-label={t("common.close")} className="close-btn" onClick={editor.close}><Icon name="close" size={20} /></button>
        </div>
        <Meta editor={editor} playlist={playlist} />
        <Outputs editor={editor} playlist={playlist} />
        <div className="rl-pl-search-bar">
          <Icon name="search" size={18} style={{ opacity: 0.5 }} />
          <SearchBox className="rl-pl-search-input" placeholder={t("radioLibrary.addTracksSearch")} value={query} onChange={setQuery} suggestions={suggestions} />
          {query && <button aria-label={t("common.clear")} type="button" className="rl-pl-search-clear" onClick={() => setQuery("")}><Icon name="close" size={16} /></button>}
        </div>
        <div className="rl-pl-list">
          {query.trim()
            ? <AddableTracks editor={editor} playlist={playlist} coverUrl={coverUrl} tracks={tracks} query={query} />
            : <PlaylistItems editor={editor} playlist={playlist} coverUrl={coverUrl} />}
        </div>
      </div>
    </>
  );
}
