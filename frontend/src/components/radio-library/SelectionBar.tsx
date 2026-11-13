"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import type { PlaylistSummary, TagEntry } from "./types";
import type { TrackSelection } from "./useTrackSelection";

interface Props {
  selection: TrackSelection;
  tags: TagEntry[];
  playlists: PlaylistSummary[];
}

const TAG_ICONS = { all: "check_box", some: "indeterminate_check_box", none: "check_box_outline_blank" } as const;

function TagMenu({ selection, tags }: Omit<Props, "playlists">) {
  const { t } = useAppSettings();
  return (
    <div className="rl-popover" onClick={(e) => e.stopPropagation()}>
      <div className="rl-popover-title">{t("radioLibrary.bulkTagTitle")}</div>
      {tags.length === 0 ? <p className="rl-empty-note">{t("radioLibrary.noTags")}</p> : tags.map((tag) => {
        const state = selection.tagState(tag.name);
        return (
          <button key={tag.id} type="button" className="rl-popover-item" onClick={() => selection.applyTag(tag.name, state !== "all")}>
            <Icon name={TAG_ICONS[state]} size={18} />
            <span>{tag.name}</span>
          </button>
        );
      })}
    </div>
  );
}

function PlaylistMenu({ selection, playlists }: Omit<Props, "tags">) {
  const { t } = useAppSettings();
  return (
    <div className="rl-popover" onClick={(e) => e.stopPropagation()}>
      <div className="rl-popover-title">{t("radioLibrary.addToPlaylistTitle")}</div>
      {playlists.length === 0 ? <p className="rl-empty-note">{t("radioLibrary.noPlaylists")}</p> : playlists.map((p) => (
        <button key={p.id} type="button" className="rl-popover-item" onClick={() => selection.addToPlaylist(p.id)}>
          <Icon name={p.is_default ? "star" : "queue_music"} size={16} filled={p.is_default} />
          <span>{p.name}</span>
        </button>
      ))}
    </div>
  );
}

export default function SelectionBar({ selection, tags, playlists }: Props) {
  const { t } = useAppSettings();
  const toggleMenu = (menu: "tag" | "playlist") => selection.setMenu(selection.menu === menu ? null : menu);
  return (
    <div className="rl-selection-bar">
      <button type="button" className="rl-sel-close" onClick={selection.clear} title={t("radioLibrary.clearSelection")}><Icon name="close" size={18} /></button>
      <span className="rl-sel-count">{t("radioLibrary.selectionCount", { count: selection.selected.size })}</span>
      <div className="rl-toolbar-spacer" />
      <div className="rl-bulk-wrap">
        <button type="button" className="btn btn-secondary" onClick={() => toggleMenu("tag")}><Icon name="label" size={16} /> {t("radioLibrary.bulkTag")}</button>
        {selection.menu === "tag" && <TagMenu selection={selection} tags={tags} />}
      </div>
      <div className="rl-bulk-wrap">
        <button type="button" className="btn btn-secondary" onClick={() => toggleMenu("playlist")}><Icon name="playlist_add" size={16} /> {t("radioLibrary.bulkAddToPlaylist")}</button>
        {selection.menu === "playlist" && <PlaylistMenu selection={selection} playlists={playlists} />}
      </div>
      <button type="button" className="btn btn-danger" onClick={() => selection.setConfirmDelete(true)}><Icon name="delete" size={16} /> {t("radioLibrary.delete")}</button>
    </div>
  );
}
