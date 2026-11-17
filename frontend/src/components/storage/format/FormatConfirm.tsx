import React from "react";
import { fsLabel } from "@/lib/storage/advice";
import type { FormatFs, FormatPlan } from "@/lib/storage/format";
import type { T } from "../common";

interface FormatConfirmProps {
  plan: FormatPlan;
  fs: FormatFs;
  label: string;
  typed: string;
  onTyped: (value: string) => void;
  acknowledged: boolean;
  onAcknowledged: (value: boolean) => void;
  secondsLeft: number;
  t: T;
}

export default function FormatConfirm({ plan, fs, label, typed, onTyped, acknowledged, onAcknowledged, secondsLeft, t }: FormatConfirmProps) {
  return (
    <div className="dv-detail">
      <div className="fmt-erase" role="alert">
        <strong>{t("storage.format.summary", { name: plan.target.name, fs: fsLabel(fs), label: label.trim() })}</strong>
        <span className="dv-sub">{t("storage.format.warning")}</span>
      </div>
      <div className="fmt-field">
        <label htmlFor="fmt-confirm" className="dv-title">{t(`storage.format.confirmMode.${plan.confirm.mode}`, { value: plan.confirm.expected })}</label>
        <input id="fmt-confirm" className="form-control" value={typed} onChange={(e) => onTyped(e.target.value)} autoComplete="off" autoCapitalize="off" spellCheck={false} />
      </div>
      <label className="st-check st-check--chip">
        <input type="checkbox" checked={acknowledged} onChange={(e) => onAcknowledged(e.target.checked)} />
        <span>{t("storage.format.ack")}</span>
      </label>
      {secondsLeft > 0 && <p className="dv-sub fmt-count" role="status">{t("storage.format.wait", { count: secondsLeft })}</p>}
    </div>
  );
}
