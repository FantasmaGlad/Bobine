"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { ShowToast } from "@/lib/useToast";

import { sendJson } from "./api";
import type { Filter, TagEntry } from "./types";
import type { RadioCatalog } from "./useRadioCatalog";
import type { TrackFilter } from "./useTrackFilter";

interface Props {
  catalog: RadioCatalog;
  filter: TrackFilter;
  showToast: ShowToast;
  onFilter: (filter: Filter) => void;
}

function useTagActions({ catalog, filter, showToast }: Omit<Props, "onFilter">) {
  const { t } = useAppSettings();
  const fail = () => showToast(t("radioLibrary.tagError"), "error");

  const create = async (name: string): Promise<boolean> => {
    try {
      const res = await sendJson("/radio/tags", "POST", { name });
      if (res.ok) {
        showToast(t("radioLibrary.tagCreatedToast"));
        catalog.refreshAll();
        return true;
      }
      if (res.status === 409) showToast(t("radioLibrary.tagExists"), "warning");
      else fail();
    } catch {
      fail();
    }
    return false;
  };

  const rename = async (tag: TagEntry) => {
    const name = window.prompt(t("radioLibrary.renameTag"), tag.name);
    if (!name || name.trim() === tag.name) return;
    try {
      const res = await sendJson(`/radio/tags/${tag.id}`, "PUT", { name: name.trim() });
      if (res.ok) catalog.refreshAll();
      else fail();
    } catch {
      fail();
    }
  };

  const remove = async (tag: TagEntry) => {
    if (!window.confirm(t("radioLibrary.deleteTagConfirm", { name: tag.name }))) return;
    try {
      const res = await sendJson(`/radio/tags/${tag.id}`, "DELETE");
      if (!res.ok) return fail();
      showToast(t("radioLibrary.tagDeletedToast"));
      if (filter.filter?.type === "tag" && filter.filter.value === tag.name) filter.clear();
      catalog.refreshAll();
    } catch {
      fail();
    }
  };

  return { create, rename, remove };
}

function TagCards({ catalog, actions, onFilter }: { catalog: RadioCatalog; actions: ReturnType<typeof useTagActions>; onFilter: (filter: Filter) => void }) {
  const { t } = useAppSettings();
  if (catalog.tags.length === 0) return <p className="rl-empty-note">{t("radioLibrary.noTags")}</p>;
  return (
    <div className="rl-cards rl-cards--compact">
      {catalog.tags.map((tag) => (
        <div key={tag.id} className="rl-tagcard glass-interactive">
          <button type="button" className="rl-tagcard-main" onClick={() => onFilter({ type: "tag", value: tag.name })}>
            <Icon name="label" size={18} />
            <span className="rl-pcard-title" title={tag.name}>{tag.name}</span>
            <span className="rl-nav-count">{tag.track_count}</span>
          </button>
          <button type="button" className="rl-tagcard-btn" title={t("radioLibrary.renameTag")} onClick={() => actions.rename(tag)}><Icon name="edit" size={15} /></button>
          <button type="button" className="rl-tagcard-btn" title={t("radioLibrary.deleteTag")} onClick={() => actions.remove(tag)}><Icon name="delete" size={15} /></button>
        </div>
      ))}
    </div>
  );
}

function GenreCards({ filter, onFilter }: Pick<Props, "filter" | "onFilter">) {
  const { t } = useAppSettings();
  if (filter.genres.length === 0) return <p className="rl-empty-note">{t("radioLibrary.noGenres")}</p>;
  return (
    <div className="rl-cards rl-cards--compact">
      {filter.genres.map((g) => (
        <div key={g.name} className="rl-tagcard glass-interactive">
          <button type="button" className="rl-tagcard-main" onClick={() => onFilter({ type: "genre", value: g.name })}>
            <Icon name="graphic_eq" size={18} />
            <span className="rl-pcard-title" title={g.name}>{g.name}</span>
            <span className="rl-nav-count">{g.count}</span>
          </button>
        </div>
      ))}
    </div>
  );
}

export default function TagsSection(props: Props) {
  const { t } = useAppSettings();
  const [name, setName] = useState("");
  const actions = useTagActions(props);
  const create = async () => {
    if (name.trim() && (await actions.create(name.trim()))) setName("");
  };
  return (
    <>
      <div className="rl-toolbar sticky-glass-toolbar">
        <div className="rl-create-row rl-create-row--wide">
          <input type="text" className="form-control" placeholder={t("radioLibrary.newTagPlaceholder")} value={name}
            onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") create(); }} />
          <button type="button" className="btn btn-primary" onClick={create} disabled={!name.trim()}>
            <Icon name="add" size={16} /> {t("radioLibrary.create")}
          </button>
        </div>
      </div>
      <h4 className="rl-block-title">{t("radioLibrary.tagsTitle")} <span className="rl-nav-count">{props.catalog.tags.length}</span></h4>
      <TagCards catalog={props.catalog} actions={actions} onFilter={props.onFilter} />
      <h4 className="rl-block-title">{t("radioLibrary.genresTitle")} <span className="rl-nav-count">{props.filter.genres.length}</span></h4>
      <GenreCards filter={props.filter} onFilter={props.onFilter} />
    </>
  );
}
