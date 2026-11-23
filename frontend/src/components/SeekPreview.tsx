"use client";

import { tileAt, type Storyboard } from "@/lib/storyboard";

export default function SeekPreview({ ratio, seconds, title, board }: { ratio: number; seconds: number; title: string; board: Storyboard | null }) {
  if (!title && !board) return null;
  const tile = board ? tileAt(board, seconds) : null;
  return (
    <span className="seek-preview" style={{ left: `${ratio * 100}%`, transform: `translateX(-${ratio * 100}%)` }}>
      {board && tile && (
        <span className="seek-preview-image" aria-hidden="true" style={{
          width: board.tile_width,
          height: board.tile_height,
          backgroundImage: `url("${board.sheets[tile.sheet]}")`,
          backgroundSize: `${board.columns * board.tile_width}px ${board.rows * board.tile_height}px`,
          backgroundPosition: `-${tile.x}px -${tile.y}px`,
        }} />
      )}
      {title && <span className="seek-preview-title">{title}</span>}
    </span>
  );
}
