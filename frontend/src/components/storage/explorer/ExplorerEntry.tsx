"use client";

import Icon from "@/components/Icon";
import { isSelectable, joinPath } from "@/lib/storage/browse";
import { formatBytes } from "@/lib/storage/display";
import { type BrowseEntry } from "@/lib/storage/types";
import { type StorageCtx } from "../common";

function entryIcon(entry: BrowseEntry): string {
  if (entry.type === "dir") return "folder";
  switch (entry.media) {
    case "video": return "movie";
    case "audio": return "music_note";
    case "image": return "image";
    case "subtitle": return "subtitles";
    default: return "draft";
  }
}

export default function ExplorerEntry({ t, lang, entry, path, isSelected, onToggle, goTo }: {
  t: StorageCtx["t"]; lang: StorageCtx["lang"]; entry: BrowseEntry; path: string; isSelected: boolean; onToggle: () => void; goTo: (target: string) => void;
}) {
  const canSelect = isSelectable(entry);
  return (
    <div className={`dv-row glass-interactive${isSelected ? " is-selected" : ""}${canSelect ? "" : " off"}`}>
      {canSelect ? (
        <label className="st-check" aria-label={entry.name}>
          <input type="checkbox" checked={isSelected} onChange={onToggle} />
        </label>
      ) : <span className="st-check-gap" />}
      {entry.type === "dir" ? (
        <button type="button" className="st-entry" onClick={() => goTo(joinPath(path, entry.name))}>
          <span className="dv-icon"><Icon name="folder" size={22} /></span>
          <span className="dv-text"><span className="dv-title">{entry.name}</span></span>
          <span className="dv-chevron"><Icon name="chevron_right" size={20} /></span>
        </button>
      ) : (
        <div className="st-entry st-entry--file">
          <span className="dv-icon"><Icon name={entryIcon(entry)} size={22} /></span>
          <span className="dv-text">
            <span className="dv-title">{entry.name}{entry.indexed && <span className="dv-badge"><Icon name="check" size={12} /> {t("storage.explorer.inLibrary")}</span>}</span>
            <span className="dv-sub">{formatBytes(entry.size, lang)}</span>
          </span>
        </div>
      )}
    </div>
  );
}
