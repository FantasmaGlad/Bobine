"use client";

import { tileAt, type Storyboard } from "@/lib/storyboard";

const SCALE = 1.5;

export default function SeekPreview({ ratio, seconds, title, board }: { ratio: number; seconds: number; title: string; board: Storyboard | null }) {
  if (!title && !board) return null;
  const tile = board ? tileAt(board, seconds) : null;
  return (
    <span className="seek-preview" style={{ left: `${ratio * 100}%`, transform: `translateX(-${ratio * 100}%)` }}>
      {board && tile && (
        <span className="seek-preview-image" aria-hidden="true" style={{
          width: board.tile_width * SCALE,
          height: board.tile_height * SCALE,
          backgroundImage: `url("${board.url}")`,
          backgroundSize: `${board.columns * board.tile_width * SCALE}px ${board.rows * board.tile_height * SCALE}px`,
          backgroundPosition: `-${tile.x * SCALE}px -${tile.y * SCALE}px`,
        }} />
      )}
      {title && <span className="seek-preview-title">{title}</span>}
    </span>
  );
}
