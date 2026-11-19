"use client";

import Icon from "@/components/Icon";
import { fsLabel, visibleNotes } from "@/lib/storage/advice";
import { type StorageVolume } from "@/lib/storage/types";
import { tr, type StorageCtx } from "../common";

function verdictIcon(verdict: string): string {
  return verdict === "recommended" ? "verified" : verdict === "acceptable" ? "check_circle" : verdict === "discouraged" ? "warning" : "help";
}

export default function FsVerdictBlock({ t, volume, onAdvice }: { t: StorageCtx["t"]; volume: StorageVolume; onAdvice: () => void }) {
  return (
    <div className="dv-detail-block">
      <div className="dv-row">
        <span className="dv-icon"><Icon name={verdictIcon(volume.assessment.verdict)} size={22} /></span>
        <span className="dv-text">
          <span className="dv-title">{t(`storage.verdict.${volume.assessment.verdict}`)} · {fsLabel(volume.fstype)}</span>
          <span className="dv-sub">{tr(t, `storage.fsReasons.${volume.assessment.reason}`)}</span>
          {visibleNotes(volume.assessment).length > 0 && (
            <span className="dv-sub">{visibleNotes(volume.assessment).map((n) => tr(t, `storage.fsNotes.${n}`)).filter(Boolean).join(" · ")}</span>
          )}
        </span>
        <span className="dv-actions"><button type="button" className="btn btn-secondary" onClick={onAdvice}><Icon name="help" size={16} /> {t("storage.details.formatAdvice")}</button></span>
      </div>
    </div>
  );
}
