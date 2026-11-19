"use client";

import React from "react";
import Icon from "@/components/Icon";
import { canConfirmFormat, needsNewPlan, type FormatOption } from "@/lib/storage/format";
import type { ApiError } from "@/lib/apiError";
import { type StorageCtx } from "../common";
import FormatChoose from "./FormatChoose";
import FormatConfirm from "./FormatConfirm";
import FormatProgress from "./FormatProgress";
import type { useConfirmClock } from "./useConfirmClock";
import type { useFormatActions } from "./useFormatActions";
import type { useFormatPlan } from "./useFormatPlan";

export interface StageView {
  ctx: StorageCtx;
  plan: ReturnType<typeof useFormatPlan>;
  clock: ReturnType<typeof useConfirmClock>;
  actions: ReturnType<typeof useFormatActions>;
  labelIssue: string | null;
  option: FormatOption | undefined;
  choose: (next: FormatOption) => void;
  unregister: (libraryKey: string) => void;
  onClose: () => void;
}

type Rendered = { body: React.ReactNode; footer?: React.ReactNode };

function refusedStage({ ctx: { t }, plan: { windowsOrMac, loadPlan }, actions: { busy, refusalText }, unregister, onClose }: StageView, refusal: ApiError): Rendered {
    const actions = Array.isArray(refusal.extra.actions) ? (refusal.extra.actions as Array<{ id: string; key: string }>) : [];
  return {
    body: (
    <div className="dv-note dv-note--strong" role="alert">
      <Icon name="block" size={22} />
      <span>{refusalText(refusal)}</span>
    </div>
    ),
    footer: (
    <div className="dv-actions">
      {actions.filter((a) => a.id === "unregister").slice(0, 1).map((a) => (
        <button key={a.key} type="button" className="btn btn-secondary" disabled={busy} onClick={() => unregister(a.key)}>{t("storage.format.unregister")}</button>
      ))}
      {(needsNewPlan(refusal.code) || refusal.code === "format_in_use" || refusal.code === "format_busy_operation") && (
        <button type="button" className="btn btn-secondary" onClick={() => void loadPlan(windowsOrMac)}>{t("storage.format.again")}</button>
      )}
      <button type="button" className="btn btn-secondary" onClick={onClose}>{t("storage.close")}</button>
    </div>
    ),
  };
}

function chooseStage({ ctx: { t, lang }, plan: p, clock, labelIssue, option, choose, onClose }: StageView): Rendered {
  const { plan, fs, windowsOrMac, setWindowsOrMac, loadPlan, label, setLabel } = p;
  if (!plan) return { body: null };
  return {
    body: (
    <FormatChoose
      plan={plan} fs={fs} onChoose={choose} travels={windowsOrMac}
      onTravels={(checked) => { setWindowsOrMac(checked); void loadPlan(checked); }}
      label={label} onLabel={setLabel} labelIssue={labelIssue} labelMax={option?.label_max ?? 11} t={t} lang={lang}
    />
    ),
    footer: (
      <div className="dv-actions">
        <button type="button" className="btn btn-secondary" onClick={onClose}>{t("storage.format.cancelWizard")}</button>
        <button type="button" className="btn btn-primary" disabled={!fs || !!labelIssue} onClick={clock.toConfirm}>{t("storage.format.next")}</button>
      </div>
    ),
  };
}

function confirmStage({ ctx: { t }, plan: { plan, fs, label, setStage }, clock, actions: { busy, execute }, labelIssue }: StageView): Rendered {
  if (!plan || !fs) return { body: null };
  const { typed, setTyped, acknowledged, setAcknowledged, secondsLeft } = clock;
  const ready = canConfirmFormat({ typed, expected: plan.confirm.expected, acknowledged, secondsLeft, labelOk: !labelIssue });
  return {
    body: (
      <FormatConfirm
        plan={plan} fs={fs} label={label} typed={typed} onTyped={setTyped}
        acknowledged={acknowledged} onAcknowledged={setAcknowledged} secondsLeft={secondsLeft} t={t}
      />
    ),
    footer: (
      <div className="dv-actions">
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => setStage("choose")}>{t("storage.format.back")}</button>
        <button type="button" className="btn btn-danger" disabled={!ready || busy} onClick={execute}><Icon name="delete_forever" size={18} /> {t("storage.format.erase")}</button>
      </div>
    ),
  };
}

function progressStage({ ctx: { t, lang }, plan: { stage }, actions: { job, pollError, cancel }, onClose }: StageView): Rendered {
  return {
    body: <FormatProgress job={job} running={stage === "running"} pollError={pollError} t={t} lang={lang} />,
    footer: stage === "running" ? (
      <div className="dv-actions">
        {job?.can_cancel && <button type="button" className="btn btn-secondary" onClick={cancel}>{t("storage.format.cancelJob")}</button>}
      </div>
    ) : (
      <div className="dv-actions"><button type="button" className="btn btn-primary" onClick={onClose}>{t("storage.format.done")}</button></div>
    )
  };
}

export function renderStage(view: StageView): Rendered {
  const { stage, refusal, plan, fs } = view.plan;
  if (stage === "loading") return { body: <div className="rl-center-note" role="status">{view.ctx.t("storage.format.loading")}</div> };
  if (stage === "refused" && refusal) return refusedStage(view, refusal);
  if (stage === "choose" && plan) return chooseStage(view);
  if (stage === "confirm" && plan && fs) return confirmStage(view);
  if (stage === "running" || (stage === "result" && view.actions.job)) return progressStage(view);
  return { body: null };
}
