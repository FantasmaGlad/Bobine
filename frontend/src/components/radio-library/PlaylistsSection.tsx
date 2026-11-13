"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";

import type { OutputDefaults, PlaylistSummary } from "./types";
import type { RadioCatalog } from "./useRadioCatalog";

interface Props {
  catalog: RadioCatalog;
  outputDefaults: OutputDefaults | null;
  onCreate: (name: string) => Promise<boolean>;
  onOpen: (id: number) => void;
  onShowTracks: (playlist: PlaylistSummary) => void;
}

function PlaylistCard({ playlist: p, catalog, outputDefaults, onOpen, onShowTracks }: Omit<Props, "onCreate"> & { playlist: PlaylistSummary }) {
  const { t } = useAppSettings();
  const open = () => onOpen(p.id);
  return (
    <div className="rl-pcard glass-interactive" role="button" tabIndex={0} onClick={open}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } }}>
      <div className="rl-pcard-cover">
        {p.cover_track_id != null ? (
          // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
          <img src={catalog.coverUrl(p.cover_track_id)} alt="" loading="lazy" />
        ) : <Icon name="queue_music" size={36} style={{ opacity: 0.3 }} />}
        {p.is_default && <span className="rl-pcard-star" title={t("radioLibrary.setDefault")}><Icon name="star" size={14} filled /></span>}
      </div>
      <div className="rl-pcard-body">
        <span className="rl-pcard-title" title={p.name}>{p.name}</span>
        <span className="rl-pcard-meta">{t("radioLibrary.itemsInPlaylist", { count: p.item_count })} · {formatMediaDuration(p.total_duration_seconds)}</span>
        <span className="rl-pcard-badges">
          {outputDefaults?.radio_cable?.override_playlist_id === p.id && <span className="rl-card-tag"><Icon name="cable" size={11} /> {t("radioLibrary.outputCable")}</span>}
          {outputDefaults?.radio_network?.override_playlist_id === p.id && <span className="rl-card-tag"><Icon name="wifi" size={11} /> {t("radioLibrary.outputNetwork")}</span>}
        </span>
      </div>
      <div className="rl-pcard-actions">
        <button type="button" className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); onShowTracks(p); }}>
          <Icon name="library_music" size={14} /> {t("radioLibrary.viewTracks")}
        </button>
        <button type="button" className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); open(); }}>
          <Icon name="edit" size={14} /> {t("radioLibrary.editPlaylist")}
        </button>
      </div>
    </div>
  );
}

export default function PlaylistsSection(props: Props) {
  const { t } = useAppSettings();
  const [name, setName] = useState("");
  const { playlists } = props.catalog;
  const create = async () => {
    if (name.trim() && (await props.onCreate(name.trim()))) setName("");
  };
  return (
    <>
      <div className="rl-toolbar sticky-glass-toolbar">
        <div className="rl-create-row rl-create-row--wide">
          <input type="text" className="form-control" placeholder={t("radioLibrary.newPlaylistPlaceholder")} value={name}
            onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") create(); }} />
          <button type="button" className="btn btn-primary" onClick={create} disabled={!name.trim()}>
            <Icon name="add" size={16} /> {t("radioLibrary.create")}
          </button>
        </div>
        <div className="rl-toolbar-spacer" />
        <span className="rl-count">{t("radioLibrary.playlistsCount", { count: playlists.length })}</span>
      </div>
      {playlists.length === 0 ? (
        <div className="rl-empty-state">
          <Icon name="queue_music" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
          <p style={{ margin: 0, fontWeight: 600 }}>{t("radioLibrary.noPlaylists")}</p>
        </div>
      ) : (
        <div className="rl-cards">
          {playlists.map((p) => <PlaylistCard key={p.id} playlist={p} {...props} />)}
        </div>
      )}
    </>
  );
}
