import type { PlaylistSummary } from "@/components/PlaylistList";
import type { ShowToast } from "@/lib/useToast";

export type Translate = (key: string, vars?: Record<string, string | number>) => string;

export interface PlaylistEditorConfig<Item, Detail> {
  endpoint: string;
  prefix: "playlists" | "audioPlaylists";
  itemsFrom: (detail: Detail) => Item[];
  payload: (items: Item[]) => unknown[];
  t: Translate;
  showToast: ShowToast;
}

export type { PlaylistSummary };
