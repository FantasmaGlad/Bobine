export interface Storyboard {
  url: string;
  interval_seconds: number;
  count: number;
  columns: number;
  rows: number;
  tile_width: number;
  tile_height: number;
}

export interface Tile {
  x: number;
  y: number;
}

export function tileAt(board: Storyboard, seconds: number): Tile {
  const index = Math.min(board.count - 1, Math.max(0, Math.floor(seconds / board.interval_seconds)));
  return { x: (index % board.columns) * board.tile_width, y: Math.floor(index / board.columns) * board.tile_height };
}
