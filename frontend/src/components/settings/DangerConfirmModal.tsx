"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

interface DangerConfirmModalProps {
  icon: string;
  title: string;
  text: string;
  items: string[];
  phraseLabel: string;
  phrase: string;
  value: string;
  onChange: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  ready: boolean;
  busy: boolean;
  busyLabel: string;
  confirmLabel: string;
}

export default function DangerConfirmModal(props: DangerConfirmModalProps) {
  const { t } = useAppSettings();
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-error-text)" }}>
          <Icon name={props.icon} size={20} /> {props.title}
        </h3>
        <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{props.text}</p>
        <ul className="settings-uninstall-list">
          {props.items.map((item) => <li key={item}>{item}</li>)}
        </ul>
        <label className="form-label" style={{ marginBottom: "4px" }}>
          {props.phraseLabel}
        </label>
        <input
          type="text"
          className="form-control"
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          placeholder={props.phrase}
          autoFocus
        />
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={props.onCancel} disabled={props.busy}>
            {t("common.cancel")}
          </button>
          <button type="button" className="btn btn-danger" onClick={props.onConfirm} disabled={!props.ready || props.busy}>
            {props.busy ? props.busyLabel : props.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
