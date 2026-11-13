"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";

import type { RadioTrack } from "./types";

interface Props {
  track: RadioTrack;
  selected: boolean;
  coverUrl: (id: number) => string;
  onOpen: () => void;
  onToggle: () => void;
}

function Tags({ tags, max }: { tags: string[]; max: number }) {
  return (
    <>
      {tags.slice(0, max).map((tg) => <span key={tg} className="rl-card-tag">{tg}</span>)}
      {tags.length > max && <span className="rl-card-tag">+{tags.length - max}</span>}
    </>
  );
}

function Check({ selected, className, onToggle }: { selected: boolean; className: string; onToggle: () => void }) {
  const { t } = useAppSettings();
  return (
    <button
      type="button"
      className={`${className} ${selected ? "on" : ""}`}
      title={t("radioLibrary.select")}
      aria-pressed={className === "rl-list-check" ? selected : undefined}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
    >
      <Icon name={selected ? "check_circle" : "radio_button_unchecked"} size={20} filled={selected} />
    </button>
  );
}

export function TrackCard({ track, selected, coverUrl, onOpen, onToggle }: Props) {
  const { t } = useAppSettings();
  return (
    <div className={`video-card rl-card ${selected ? "selected" : ""}`} onClick={onOpen}>
      <Check selected={selected} className="rl-card-check" onToggle={onToggle} />
      <div className="thumbnail-wrapper rl-thumb">
        {track.has_cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
          <img src={coverUrl(track.id)} alt="" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <Icon name="music_note" size={40} style={{ opacity: 0.25 }} />
        )}
        <span className="card-duration">{formatMediaDuration(track.duration_seconds)}</span>
      </div>
      <div className="card-content">
        <h4 className="card-title" title={track.title}>{track.title}</h4>
        <div className="card-meta-row">
          <span className="rl-card-artist">{track.artist || t("radioLibrary.unknownArtist")}</span>
        </div>
        {track.tags.length > 0 && <div className="rl-card-tags"><Tags tags={track.tags} max={3} /></div>}
      </div>
    </div>
  );
}

export function TrackRow({ track, selected, coverUrl, onOpen, onToggle }: Props) {
  const { t } = useAppSettings();
  return (
    <div className={`rl-list-row glass-interactive ${selected ? "selected is-selected" : ""}`} onClick={onOpen}>
      <Check selected={selected} className="rl-list-check" onToggle={onToggle} />
      <span className="rl-list-cover">
        {track.has_cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
          <img src={coverUrl(track.id)} alt="" loading="lazy" />
        ) : <Icon name="music_note" size={18} style={{ opacity: 0.3 }} />}
      </span>
      <span className="rl-list-text">
        <span className="rl-list-title">{track.title}</span>
        <span className="rl-list-sub">{track.artist || t("radioLibrary.unknownArtist")}{track.album ? ` — ${track.album}` : ""}</span>
      </span>
      {track.genre ? <span className="rl-list-genre">{track.genre}</span> : <span className="rl-list-genre rl-list-genre--empty" />}
      <span className="rl-list-tags"><Tags tags={track.tags} max={2} /></span>
      <span className="rl-list-duration">{formatMediaDuration(track.duration_seconds)}</span>
    </div>
  );
}
