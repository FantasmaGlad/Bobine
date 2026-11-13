"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";

interface Props {
  count: number;
  onAddToPlaylist: () => void;
  onDelete: () => void;
  onClear: () => void;
}

export default function SelectionBar({ count, onAddToPlaylist, onDelete, onClear }: Props) {
  const { t } = useAppSettings();
  return (
    <div className="interrupted-block">
      <div className="interrupted-text">
        <span className="interrupted-label">{t("library.selectionLabel")}</span>
        <span className="interrupted-title">{t("library.selectedCount", { count })}</span>
      </div>
      <div className="interrupted-actions">
        <button className="btn btn-secondary" onClick={onAddToPlaylist}>{t("library.addToPlaylist")}</button>
        <button className="btn btn-danger" onClick={onDelete}>{t("common.delete")}</button>
        <button className="btn btn-secondary" onClick={onClear}>{t("library.clearSelection")}</button>
      </div>
    </div>
  );
}
