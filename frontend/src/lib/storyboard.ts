export interface Storyboard {
  sheets: string[];
  interval_seconds: number;
  count: number;
  columns: number;
  rows: number;
  tile_width: number;
  tile_height: number;
}

export interface Tile {
  sheet: number;
  x: number;
  y: number;
}

export function tileAt(board: Storyboard, seconds: number): Tile {
  const index = Math.min(board.count - 1, Math.max(0, Math.floor(seconds / board.interval_seconds)));
  const perSheet = board.columns * board.rows;
  const within = index % perSheet;
  return { sheet: Math.floor(index / perSheet), x: (within % board.columns) * board.tile_width, y: Math.floor(within / board.columns) * board.tile_height };
}
