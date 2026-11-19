"use client";

import type { BackgroundItem } from "./types";

export default function DeleteBackgroundModal({ t, target, onCancel, onConfirm }: {
  t: (key: string) => string; target: BackgroundItem; onCancel: () => void; onConfirm: () => void;
}) {
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>{t("backgrounds.deleteBackgroundTitle")}</h3>
        <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
          {t("backgrounds.deleteBackgroundConfirmBefore")}{" "}
          <strong style={{ color: "var(--text-main)" }}>{target.title}</strong>{t("backgrounds.deleteBackgroundConfirmAfter")}
        </p>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            {t("common.cancel")}
          </button>
          <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={onConfirm}>
            {t("backgrounds.confirmDelete")}
          </button>
        </div>
      </div>
    </div>
  );
}
