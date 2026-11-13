"use client";

import { useRef, useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";
import { matchesQuery } from "@/lib/searchText";

import type { PlaylistDetail, RadioTrack } from "./types";
import type { PlaylistEditor } from "./usePlaylistEditor";

interface Props {
  editor: PlaylistEditor;
  playlist: PlaylistDetail;
  coverUrl: (id: number) => string;
}

function Thumb({ hasCover, id, coverUrl }: { hasCover: boolean; id: number; coverUrl: (id: number) => string }) {
  return (
    <div className="rl-pl-row-thumb">
      {hasCover ? (
        <img src={coverUrl(id)} alt="" />
      ) : <Icon name="music_note" size={18} style={{ opacity: 0.3 }} />}
    </div>
  );
}

function RowText({ title, artist }: { title: string; artist: string | null }) {
  const { t } = useAppSettings();
  return (
    <div className="rl-pl-row-text">
      <span className="rl-pl-row-title">{title}</span>
      <span className="rl-pl-row-artist">{artist || t("radioLibrary.unknownArtist")}</span>
    </div>
  );
}

export function AddableTracks({ editor, playlist, coverUrl, tracks, query }: Props & { tracks: RadioTrack[]; query: string }) {
  const { t } = useAppSettings();
  const shown = tracks.filter((tr) => matchesQuery(`${tr.title} ${tr.artist ?? ""} ${tr.album ?? ""}`, query));
  if (shown.length === 0) return <p className="rl-empty-note" style={{ padding: "16px" }}>{t("radioLibrary.noResults")}</p>;
  return (
    <>
      {shown.map((tr) => {
        const already = playlist.items.some((i) => i.track.id === tr.id);
        return (
          <div key={tr.id} className="rl-pl-row">
            <Thumb hasCover={tr.has_cover} id={tr.id} coverUrl={coverUrl} />
            <RowText title={tr.title} artist={tr.artist} />
            <button
              type="button"
              className={`rl-pl-row-action ${already ? "on" : ""}`}
              disabled={editor.addingTrackId === tr.id}
              onClick={() => (already ? editor.removeTrack(tr.id) : editor.addTrack(tr.id))}
              title={already ? t("radioLibrary.remove") : t("radioLibrary.add")}
            >
              <Icon name={already ? "check_circle" : "add_circle"} size={26} filled={already} />
            </button>
          </div>
        );
      })}
    </>
  );
}

export function PlaylistItems({ editor, playlist, coverUrl }: Props) {
  const { t } = useAppSettings();
  const dragIndex = useRef<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  if (playlist.items.length === 0) {
    return (
      <div className="rl-empty-state" style={{ padding: "32px 16px" }}>
        <Icon name="queue_music" size={36} style={{ opacity: 0.25, marginBottom: "8px" }} />
        <p style={{ margin: 0 }}>{t("radioLibrary.emptyPlaylist")}</p>
      </div>
    );
  }
  const drop = (index: number) => {
    const from = dragIndex.current;
    dragIndex.current = null;
    setOverIndex(null);
    if (from !== null && from !== index) editor.move(from, index);
  };
  return (
    <>
      {playlist.items.map((item, index) => (
        <div key={item.id}
          className={`rl-pl-row ${overIndex === index ? "drag-over" : ""}`}
          draggable
          onDragStart={() => { dragIndex.current = index; }}
          onDragOver={(e) => { e.preventDefault(); setOverIndex(index); }}
          onDragLeave={() => setOverIndex((cur) => (cur === index ? null : cur))}
          onDrop={(e) => { e.preventDefault(); drop(index); }}
          onDragEnd={() => { dragIndex.current = null; setOverIndex(null); }}
        >
          <Icon name="drag_indicator" size={18} className="rl-drag-handle" />
          <Thumb hasCover={item.track.has_cover} id={item.track.id} coverUrl={coverUrl} />
          <RowText title={item.track.title} artist={item.track.artist} />
          <span className="rl-pl-row-duration">{formatMediaDuration(item.track.duration_seconds)}</span>
          <button type="button" className="rl-pl-row-action" title={t("radioLibrary.remove")} onClick={() => editor.removeTrack(item.track.id)}>
            <Icon name="close" size={18} />
          </button>
        </div>
      ))}
    </>
  );
}
