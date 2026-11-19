"use client";

import Icon from "@/components/Icon";
import { breadcrumbs } from "@/lib/storage/browse";
import { type TransferKind } from "@/lib/storage/types";
import { type StorageCtx } from "./common";
import ExplorerCrumbs from "./explorer/ExplorerCrumbs";
import ExplorerEntry from "./explorer/ExplorerEntry";
import SelectionBar from "./explorer/SelectionBar";
import { useBrowse } from "./explorer/useBrowse";
import { useExplorerSelection } from "./explorer/useExplorerSelection";
import { useTransferStart } from "./explorer/useTransferStart";

interface Props extends StorageCtx {
  volumeKey: string;
  name: string;
  portable: boolean;
  canExtend: boolean;
  registered: boolean;
  onClose: () => void;
  onJob: (jobId: string, mode: "import" | "index") => void;
  onLibraryChanged: () => void;
}
export default function Explorer({ volumeKey, name, portable, canExtend, registered, onClose, onJob, onLibraryChanged, t, lang, notify }: Props) {
  const { path, entries, meta, loading, loadMore, goTo } = useBrowse(volumeKey, { t, lang, notify });
  const { selected, setSelected, chosen, kind, setKind, setKindTouched, toggle, selectable, allSelected, toggleAll } = useExplorerSelection(entries);
  const { busy, start } = useTransferStart({ volumeKey, registered, chosen, kind, clearSelection: () => setSelected({}), onJob, onLibraryChanged, ctx: { t, lang, notify } });

  const crumbs = breadcrumbs(path);
  const onKind = (next: TransferKind) => { setKind(next); setKindTouched(true); };

  return (
    <div className="dv-section st-explorer">
      <div className="dv-toolbar">
        <button type="button" className="btn btn-secondary" onClick={onClose}><Icon name="arrow_back" size={16} /> {t("storage.back")}</button>
        <ExplorerCrumbs t={t} crumbs={crumbs} rootName={name} goTo={goTo} />
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
          {entries.map((entry) => (
            <ExplorerEntry key={entry.path} t={t} lang={lang} entry={entry} path={path} isSelected={!!selected[entry.path]} onToggle={() => toggle(entry)} goTo={goTo} />
          ))}
          {entries.length < meta.total && (
            <button type="button" className="btn btn-secondary" disabled={loading} onClick={loadMore}>{t("storage.explorer.more")}</button>
          )}
          {(meta.truncated || meta.skipped_links > 0) && (
            <p className="dv-sub">
              {meta.truncated ? t("storage.explorer.truncated") : ""} {meta.skipped_links > 0 ? t("storage.explorer.links", { count: meta.skipped_links }) : ""}
            </p>
          )}
        </div>
      )}
      {chosen.length > 0 && (
        <SelectionBar t={t} lang={lang} chosen={chosen} kind={kind} onKind={onKind} busy={busy} canExtend={canExtend} portable={portable} start={start} />
      )}
    </div>
  );
}
