"use client";

import React from "react";
import type { Translate } from "./types";

interface PlaylistDeleteDialogProps {
  prefix: string;
  t: Translate;
  name: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function PlaylistDeleteDialog({ prefix, t, name, onConfirm, onCancel }: PlaylistDeleteDialogProps) {
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 style={{ fontSize: "1.1rem", margin: "0 0 12px" }}>{t(`${prefix}.deletePlaylistTitle`)}</h3>
        <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: "0 0 20px", lineHeight: 1.5 }}>
          {t(`${prefix}.deletePlaylistConfirmBefore`)} <strong style={{ color: "var(--text-main)" }}>{name}</strong>{t(`${prefix}.deletePlaylistConfirmAfter`)}
        </p>
        <div className="modal-actions">
          <button className="btn btn-danger" onClick={onConfirm}>{t("common.delete")}</button>
          <button className="btn btn-secondary" onClick={onCancel}>{t("common.cancel")}</button>
        </div>
      </div>
    </div>
  );
}
