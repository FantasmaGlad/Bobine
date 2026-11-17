import React from "react";
import Icon from "@/components/Icon";
import { fsLabel, visibleNotes } from "@/lib/storage/advice";
import { formatBytes } from "@/lib/storage/display";
import type { FormatFs, FormatOption } from "@/lib/storage/format";
import { tr, type Lang, type T } from "../common";

interface FormatOptionsProps {
  options: FormatOption[];
  fs: FormatFs | null;
  onChoose: (option: FormatOption) => void;
  t: T;
  lang: Lang;
}

function optionLine(o: FormatOption, t: T): string {
  return o.available
    ? `${t(`storage.verdict.${o.verdict}`)} · ${tr(t, `storage.fsReasons.${o.reason}`)}`
    : tr(t, `storage.format.unavailable.${o.unavailable}`, "", { package: o.install_package ?? "" });
}

export default function FormatOptions({ options, fs, onChoose, t, lang }: FormatOptionsProps) {
  return (
    <div className="dv-detail-block">
      <h4>{t("storage.format.formatTitle")}</h4>
      <div className="fmt-options" role="radiogroup" aria-label={t("storage.format.formatTitle")}>
        {options.map((o) => {
          const notes = visibleNotes({ reason: o.reason, notes: o.notes.filter((n) => n !== "quick_format_only") }, 3);
          return (
            <label key={o.fs} className="fmt-option glass-interactive" aria-disabled={!o.available}>
              <input type="radio" name="fmt-fs" checked={fs === o.fs} disabled={!o.available} onChange={() => onChoose(o)} />
              <span className="dv-text">
                <span className="dv-title">
                  {fsLabel(o.fs)}
                  {o.recommended && <span className="dv-badge">{t("storage.format.recommended")}</span>}
                </span>
                <span className="dv-sub">{optionLine(o, t)}</span>
                {o.available && notes.length > 0 && <span className="dv-sub">{notes.map((n) => tr(t, `storage.fsNotes.${n}`)).filter(Boolean).join(" · ")}</span>}
                {o.available && o.fs === "exfat" && o.cluster_bytes && <span className="dv-sub">{t("storage.format.cluster", { size: formatBytes(o.cluster_bytes, lang) })}</span>}
              </span>
            </label>
          );
        })}
      </div>
      <p className="dv-sub"><Icon name="info" size={14} /> {t("storage.fsNotes.quick_format_only")}</p>
    </div>
  );
}
