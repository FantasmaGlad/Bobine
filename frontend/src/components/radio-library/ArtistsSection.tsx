"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import type { Filter } from "./types";
import type { RadioCatalog } from "./useRadioCatalog";

interface Props {
  catalog: RadioCatalog;
  onFilter: (filter: Filter) => void;
}

function Artists({ catalog, onFilter }: Props) {
  const { t } = useAppSettings();
  if (catalog.artists.length === 0) return <div className="rl-center-note">{t("radioLibrary.noResults")}</div>;
  return (
    <div className="rl-cards">
      {catalog.artists.map((a) => (
        <button key={a.name} type="button" className="rl-pcard rl-pcard--simple glass-interactive" onClick={() => onFilter({ type: "artist", value: a.name })}>
          <div className="rl-pcard-cover rl-pcard-cover--round"><Icon name="person" size={32} style={{ opacity: 0.35 }} /></div>
          <div className="rl-pcard-body">
            <span className="rl-pcard-title" title={a.name}>{a.name}</span>
            <span className="rl-pcard-meta">{t("radioLibrary.itemsInPlaylist", { count: a.track_count })} · {t("radioLibrary.albumsCount", { count: a.album_count })}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function Albums({ catalog, onFilter }: Props) {
  const { t } = useAppSettings();
  if (catalog.albums.length === 0) return <div className="rl-center-note">{t("radioLibrary.noResults")}</div>;
  return (
    <div className="rl-cards">
      {catalog.albums.map((al) => (
        <button key={`${al.album}-${al.album_artist ?? ""}`} type="button" className="rl-pcard rl-pcard--simple glass-interactive" onClick={() => onFilter({ type: "album", value: al.album })}>
          <div className="rl-pcard-cover">
            {al.cover_track_id != null ? (
              <img src={catalog.coverUrl(al.cover_track_id)} alt="" loading="lazy" />
            ) : <Icon name="album" size={36} style={{ opacity: 0.3 }} />}
          </div>
          <div className="rl-pcard-body">
            <span className="rl-pcard-title" title={al.album}>{al.album}</span>
            <span className="rl-pcard-meta">{al.album_artist || t("radioLibrary.unknownArtist")}{al.year ? ` · ${al.year}` : ""} · {t("radioLibrary.itemsInPlaylist", { count: al.track_count })}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

export default function ArtistsSection(props: Props) {
  const { t } = useAppSettings();
  const [view, setView] = useState<"artists" | "albums">("artists");
  const { artists, albums } = props.catalog;
  return (
    <>
      <div className="rl-toolbar sticky-glass-toolbar">
        <div className="view-toggle" role="group">
          <button type="button" className={`view-btn ${view === "artists" ? "active" : ""}`} onClick={() => setView("artists")}>
            <Icon name="person" size={16} /> {t("radioLibrary.artistsTitle")}
          </button>
          <button type="button" className={`view-btn ${view === "albums" ? "active" : ""}`} onClick={() => setView("albums")}>
            <Icon name="album" size={16} /> {t("radioLibrary.albumsTitle")}
          </button>
        </div>
        <div className="rl-toolbar-spacer" />
        <span className="rl-count">{view === "artists" ? artists.length : albums.length}</span>
      </div>
      {view === "artists" ? <Artists {...props} /> : <Albums {...props} />}
    </>
  );
}
