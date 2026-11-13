"use client";

import React from "react";

interface Props {
  title: React.ReactNode;
  children?: React.ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
  confirmDisabled?: boolean;
}

export default function ConfirmDialog({ title, children, confirmLabel, cancelLabel, onConfirm, onCancel, danger, confirmDisabled }: Props) {
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>{title}</h3>
        {children}
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            style={danger ? { backgroundColor: "var(--accent-error)" } : undefined}
            onClick={onConfirm}
            disabled={confirmDisabled}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
