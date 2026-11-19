"use client";

import Icon from "@/components/Icon";
import SegmentedTabs from "@/components/SegmentedTabs";
import { selectionBytes } from "@/lib/storage/browse";
import { formatBytes } from "@/lib/storage/display";
import { type BrowseEntry, type TransferKind } from "@/lib/storage/types";
import { type StorageCtx } from "../common";

export default function SelectionBar({ t, lang, chosen, kind, onKind, busy, canExtend, portable, start }: {
  t: StorageCtx["t"]; lang: StorageCtx["lang"]; chosen: BrowseEntry[]; kind: TransferKind; onKind: (kind: TransferKind) => void;
  busy: boolean; canExtend: boolean; portable: boolean; start: (mode: "import" | "index") => void;
}) {
  const bytes = selectionBytes(chosen);
  return (
    <div className="st-bar" role="region" aria-label={t("storage.explorer.selected", { count: chosen.length })}>
      <div className="st-bar-head">
        <strong>{t("storage.explorer.selected", { count: chosen.length })}{bytes > 0 ? ` · ${formatBytes(bytes, lang)}` : ""}</strong>
        <SegmentedTabs
          ariaLabel={t("storage.explorer.destination")}
          value={kind}
          onChange={(id) => onKind(id as TransferKind)}
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
  );
}
