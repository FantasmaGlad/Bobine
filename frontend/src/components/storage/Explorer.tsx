"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Icon from "@/components/Icon";
import SegmentedTabs from "@/components/SegmentedTabs";
import {
  breadcrumbs, encodeKey, formatBytes, isSelectable, joinPath, selectableEntries, selectionBytes, storageRequest, suggestKind, toggleSelection,
  type BrowseEntry, type BrowseResult, type TransferKind, type TransferStart,
} from "@/lib/storageApi";
import { storageErrorText, type StorageCtx } from "./common";

interface Props extends StorageCtx {
  volumeKey: string;
  name: string;
  portable: boolean;
  /** Le support peut devenir une bibliothèque externe (UUID connu, pas un téléphone). */
  canExtend: boolean;
  registered: boolean;
  onClose: () => void;
  onJob: (jobId: string, mode: "import" | "index") => void;
  onLibraryChanged: () => void;
}

const PAGE = 200;

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

/** Explorateur d'un support : dossiers, médias, sélection, puis UNE barre d'actions (Importer / Utiliser comme extension). */
export default function Explorer({ volumeKey, name, portable, canExtend, registered, onClose, onJob, onLibraryChanged, t, lang, notify }: Props) {
  const [path, setPath] = useState("");
  const [entries, setEntries] = useState<BrowseEntry[]>([]);
  const [meta, setMeta] = useState<Pick<BrowseResult, "total" | "truncated" | "skipped_links">>({ total: 0, truncated: false, skipped_links: 0 });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Record<string, BrowseEntry>>({});
  const [kind, setKind] = useState<TransferKind>("video");
  const [kindTouched, setKindTouched] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (target: string, offset = 0) => {
      setLoading(true);
      const query = new URLSearchParams({ path: target, offset: String(offset), limit: String(PAGE), media_only: "true" });
      const result = await storageRequest<BrowseResult>(`/volumes/${encodeKey(volumeKey)}/browse?${query}`);
      setLoading(false);
      if (!result.ok) {
        notify(storageErrorText(result.error, t, lang), "error");
        return;
      }
      setEntries((prev) => (offset === 0 ? result.data.entries : [...prev, ...result.data.entries]));
      setMeta({ total: result.data.total, truncated: result.data.truncated, skipped_links: result.data.skipped_links });
    },
    [volumeKey, notify, t, lang],
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement d'un dossier du support (API)
    void load(path);
  }, [load, path]);

  const chosen = useMemo(() => Object.values(selected), [selected]);
  useEffect(() => {
    // La nature proposée suit la sélection tant que l'utilisateur ne l'a pas choisie lui-même.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- dérivé de la sélection
    if (!kindTouched && chosen.length) setKind(suggestKind(chosen));
  }, [chosen, kindTouched]);

  const toggle = (entry: BrowseEntry) =>
    setSelected((prev) => {
      const next = { ...prev };
      if (toggleSelection(Object.keys(prev), entry.path).includes(entry.path)) next[entry.path] = entry;
      else delete next[entry.path];
      return next;
    });

  const selectable = selectableEntries(entries);
  const allSelected = selectable.length > 0 && selectable.every((e) => selected[e.path]);
  const toggleAll = () =>
    setSelected((prev) => {
      const next = { ...prev };
      for (const entry of selectable) {
        if (allSelected) delete next[entry.path];
        else next[entry.path] = entry;
      }
      return next;
    });

  const start = async (mode: "import" | "index") => {
    if (chosen.length === 0) return;
    setBusy(true);
    try {
      if (mode === "index" && !registered) {
        const reg = await storageRequest(`/volumes/${encodeKey(volumeKey)}/library`, { body: {} });
        if (!reg.ok) {
          notify(storageErrorText(reg.error, t, lang), "error");
          return;
        }
        notify(t("storage.extension.started"), "success");
        onLibraryChanged();
      }
      const result = await storageRequest<TransferStart>(`/volumes/${encodeKey(volumeKey)}/${mode}`, {
        body: { entries: chosen.map((e) => ({ path: e.path })), kind },
      });
      if (!result.ok) {
        notify(storageErrorText(result.error, t, lang), "error");
        return;
      }
      if (result.data.job_id) {
        onJob(result.data.job_id, mode);
        setSelected({});
      } else {
        notify(t("storage.job.doneNone"), "warning");
      }
    } finally {
      setBusy(false);
    }
  };

  const bytes = selectionBytes(chosen);
  const crumbs = breadcrumbs(path);
  const goTo = (target: string) => {
    setPath(target);
    setEntries([]);
  };

  return (
    <div className="dv-section st-explorer">
      <div className="dv-toolbar">
        <button type="button" className="btn btn-secondary" onClick={onClose}><Icon name="arrow_back" size={16} /> {t("storage.back")}</button>
        <nav className="st-crumbs" aria-label={t("storage.explorer.root")}>
          {crumbs.map((crumb, index) => (
            <span key={crumb.path} className="st-crumb">
              {index > 0 && <Icon name="chevron_right" size={16} />}
              <button type="button" className="dv-link-btn" aria-current={index === crumbs.length - 1 ? "page" : undefined} onClick={() => goTo(crumb.path)}>
                {crumb.label ?? name}
              </button>
            </span>
          ))}
        </nav>
      </div>

      {loading && entries.length === 0 ? (
        <div className="rl-center-note">{t("storage.loading")}</div>
      ) : entries.length === 0 ? (
        <div className="rl-empty-state"><Icon name="folder_off" size={36} style={{ opacity: 0.3 }} /><p style={{ margin: 0 }}>{t("storage.explorer.empty")}</p></div>
      ) : (
        <div className="dv-list">
          {selectable.length > 1 && (
            <label className="st-check st-check--all">
              <input type="checkbox" checked={allSelected} onChange={toggleAll} />
              <span>{t("storage.explorer.selectAll")}</span>
            </label>
          )}
          {entries.map((entry) => {
            const canSelect = isSelectable(entry);
            const isSelected = !!selected[entry.path];
            return (
              <div key={entry.path} className={`dv-row glass-interactive${isSelected ? " is-selected" : ""}${canSelect ? "" : " off"}`}>
                {canSelect ? (
                  <label className="st-check" aria-label={entry.name}>
                    <input type="checkbox" checked={isSelected} onChange={() => toggle(entry)} />
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
          })}
          {entries.length < meta.total && (
            <button type="button" className="btn btn-secondary" disabled={loading} onClick={() => load(path, entries.length)}>{t("storage.explorer.more")}</button>
          )}
          {(meta.truncated || meta.skipped_links > 0) && (
            <p className="dv-sub">
              {meta.truncated ? t("storage.explorer.truncated") : ""} {meta.skipped_links > 0 ? t("storage.explorer.links", { count: meta.skipped_links }) : ""}
            </p>
          )}
        </div>
      )}

      {chosen.length > 0 && (
        <div className="st-bar" role="region" aria-label={t("storage.explorer.selected", { count: chosen.length })}>
          <div className="st-bar-head">
            <strong>{t("storage.explorer.selected", { count: chosen.length })}{bytes > 0 ? ` · ${formatBytes(bytes, lang)}` : ""}</strong>
            <SegmentedTabs
              ariaLabel={t("storage.explorer.destination")}
              value={kind}
              onChange={(id) => { setKind(id as TransferKind); setKindTouched(true); }}
              tabs={(["video", "audio_course", "radio"] as TransferKind[]).map((k) => ({ id: k, label: t(`storage.explorer.kinds.${k}`) }))}
            />
          </div>
          <div className="st-bar-actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => start("import")}><Icon name="download" size={18} /> {t("storage.explorer.import")}</button>
            {canExtend && !portable && (
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => start("index")}><Icon name="hard_drive" size={18} /> {t("storage.explorer.useAsExtension")}</button>
            )}
          </div>
          <p className="dv-sub">{portable ? t("storage.explorer.hintPhone") : t("storage.explorer.hint")}</p>
        </div>
      )}
    </div>
  );
}
