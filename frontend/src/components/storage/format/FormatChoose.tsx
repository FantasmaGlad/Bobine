import React from "react";
import type { FormatFs, FormatOption, FormatPlan } from "@/lib/storage/format";
import type { Lang, T } from "../common";
import EraseSummary from "./EraseSummary";
import FormatOptions from "./FormatOptions";

interface FormatChooseProps {
  plan: FormatPlan;
  fs: FormatFs | null;
  onChoose: (option: FormatOption) => void;
  travels: boolean;
  onTravels: (value: boolean) => void;
  label: string;
  onLabel: (value: string) => void;
  labelIssue: string | null;
  labelMax: number;
  t: T;
  lang: Lang;
}

export default function FormatChoose({ plan, fs, onChoose, travels, onTravels, label, onLabel, labelIssue, labelMax, t, lang }: FormatChooseProps) {
  return (
    <div className="dv-detail">
      <EraseSummary plan={plan} t={t} lang={lang} />
      <label className="st-check st-check--chip">
        <input type="checkbox" checked={travels} onChange={(e) => onTravels(e.target.checked)} />
        <span>{t("storage.format.travels")}</span>
      </label>
      <FormatOptions options={plan.options} fs={fs} onChoose={onChoose} t={t} lang={lang} />
      <div className="fmt-field">
        <label htmlFor="fmt-label" className="dv-title">{t("storage.format.labelTitle")}</label>
        <input id="fmt-label" className="form-control" value={label} maxLength={40} onChange={(e) => onLabel(e.target.value)} aria-invalid={!!labelIssue} autoComplete="off" />
        <span className={labelIssue ? "dv-error" : "dv-sub"}>
          {labelIssue ? t(`storage.format.labelProblem.${labelIssue}`) : t("storage.format.labelHint", { max: labelMax })}
        </span>
      </div>
    </div>
  );
}
