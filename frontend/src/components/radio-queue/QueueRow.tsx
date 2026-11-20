"use client";

import React from "react";
import Icon from "@/components/Icon";
import type { RadioTrackInfo } from "@/lib/useRadioSocket";

type T = (key: string, params?: Record<string, string | number>) => string;

export function formatTrackTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "--:--";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export interface HandleEvents {
  onPointerDown: (event: React.PointerEvent<HTMLButtonElement>) => void;
  onPointerMove: (event: React.PointerEvent<HTMLButtonElement>) => void;
  onPointerUp: (event: React.PointerEvent<HTMLButtonElement>) => void;
  onPointerCancel: (event: React.PointerEvent<HTMLButtonElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLButtonElement>) => void;
}

interface RowProps {
  track: RadioTrackInfo;
  index: number;
  cover: string | null;
  offset: number;
  dragged: boolean;
  rowRef: (node: HTMLDivElement | null) => void;
  handle: HandleEvents;
  onRemove: () => void;
  t: T;
}

function TrackCover({ cover }: { cover: string | null }) {
  if (cover) return <img className="rq-cover" src={cover} alt="" loading="lazy" draggable={false} />;
  return (
    <span className="rq-cover rq-cover--empty" aria-hidden="true">
      <Icon name="music_note" size={20} style={{ opacity: 0.4 }} />
    </span>
  );
}

export default function QueueRow({ track, index, cover, offset, dragged, rowRef, handle, onRemove, t }: RowProps) {
  return (
    <div
      ref={rowRef}
      role="listitem"
      className={`rq-row${dragged ? " is-dragging" : ""}`}
      style={{
        transform: offset ? `translateY(${offset}px)` : undefined,
        transition: dragged ? "none" : "transform 140ms ease",
      }}
    >
      <button
        type="button"
        className="rq-handle"
        data-handle={index}
        aria-label={t("radioRemote.dragHandle", { title: track.title })}
        title={t("radioRemote.dragHandleHint")}
        {...handle}
      >
        <Icon name="drag_indicator" size={20} />
      </button>
      <span className="rq-pos">{index + 1}</span>
      <TrackCover cover={cover} />
      <span className="rq-text">
        <span className="rq-title">{track.title}</span>
        <span className="rq-sub">
          <span className="rq-artist">{track.artist || t("radioLibrary.unknownArtist")}</span>
          {track.genre ? <span className="rq-genre">{track.genre}</span> : null}
        </span>
      </span>
      <span className="rq-duration">{formatTrackTime(track.duration_seconds)}</span>
      <button
        type="button"
        className="rq-remove olc-press"
        aria-label={t("radioRemote.removeTrack", { title: track.title })}
        title={t("radioRemote.remove")}
        onClick={onRemove}
      >
        <Icon name="close" size={16} />
      </button>
    </div>
  );
}
