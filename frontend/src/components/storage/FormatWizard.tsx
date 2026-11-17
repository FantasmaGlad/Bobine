"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import { canConfirmFormat, canLeaveWizard, defaultFormat, formatTravels, labelProblem, needsNewPlan, reflectionLeft, refusalKey, type FormatFs, type FormatJob, type FormatOption, type FormatPlan } from "@/lib/storage/format";
import { encodeKey, storageRequest } from "@/lib/storage/request";
import type { ApiError } from "@/lib/apiError";
import { storageErrorText, tr, type StorageCtx } from "./common";
import FormatChoose from "./format/FormatChoose";
import FormatConfirm from "./format/FormatConfirm";
import FormatProgress from "./format/FormatProgress";
import { useFormatJobPolling } from "./format/useFormatJobPolling";

interface Props extends StorageCtx {
  target: { key: string; name: string; resume?: FormatJob | null } | null;
  onClose: () => void;
  onChanged: () => void;
}

type Stage = "loading" | "refused" | "choose" | "confirm" | "running" | "result";

const REFLECTION_SECONDS = 5;

export default function FormatWizard({ target, onClose, onChanged, t, lang, notify }: Props) {
  if (!target) return <Sheet open={false} onClose={onClose}>{null}</Sheet>;
  return <WizardBody key={target.key + (target.resume?.job_id ?? "")} target={target} onClose={onClose} onChanged={onChanged} t={t} lang={lang} notify={notify} />;
}

function WizardBody({ target, onClose, onChanged, t, lang, notify }: Props & { target: NonNullable<Props["target"]> }) {
  const [stage, setStage] = useState<Stage>(target.resume ? "running" : "loading");
  const [plan, setPlan] = useState<FormatPlan | null>(null);
  const [refusal, setRefusal] = useState<ApiError | null>(null);
  const [windowsOrMac, setWindowsOrMac] = useState(false);
  const [fs, setFs] = useState<FormatFs | null>(null);
  const [label, setLabel] = useState("");
  const [typed, setTyped] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const [pollError, setPollError] = useState(false);
  const [job, setJob] = useState<FormatJob | null>(target.resume ?? null);
  const finished = useRef(false);

  const loadPlan = useCallback(async (travels: boolean) => {
    setStage("loading");
    const result = await storageRequest<FormatPlan>("/format/plan", { body: { key: target.key, travels: formatTravels(travels) } });
    if (!result.ok) {
      setRefusal(result.error);
      setStage("refused");
      return;
    }
    setPlan(result.data);
    const chosen = defaultFormat(result.data);
    setFs(chosen);
    setLabel(result.data.options.find((o) => o.fs === chosen)?.label ?? "BOBINE");
    setStage("choose");
  }, [target.key]);

  useEffect(() => {
    if (!target.resume) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial d'une ressource externe (API)
      void loadPlan(false);
    }
  }, [loadPlan, target.resume]);

  useEffect(() => {
    if (stage !== "confirm") return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [stage]);

  const showResult = useCallback(() => setStage("result"), []);
  useFormatJobPolling({ active: stage === "running", job, setJob, setPollError, onResult: showResult, finished, onChanged });

  const option: FormatOption | undefined = plan?.options.find((o) => o.fs === fs);
  const labelIssue = fs ? labelProblem(fs, label) : "empty";
  const secondsLeft = reflectionLeft(startedAt, now || startedAt, REFLECTION_SECONDS);
  const refusalText = (error: ApiError) => tr(t, refusalKey(error.code), storageErrorText(error, t, lang), { package: String(error.extra.package ?? "") });

  const choose = (next: FormatOption) => {
    if (!next.available) return;
    setFs(next.fs);
    setLabel(next.label);
  };

  const toConfirm = () => {
    setTyped("");
    setAcknowledged(false);
    const start = Date.now();
    setStartedAt(start);
    setNow(start);
    setStage("confirm");
  };

  const execute = async () => {
    if (!plan || !fs) return;
    setBusy(true);
    const result = await storageRequest<{ job_id: string }>("/format/execute", {
      body: { key: target.key, token: plan.token, fs, label: label.trim(), confirm: typed, acknowledged },
    });
    setBusy(false);
    if (result.ok) {
      finished.current = false;
      const first = await storageRequest<FormatJob>(`/format/jobs/${encodeKey(result.data.job_id)}`);
      setJob(first.ok ? first.data : { job_id: result.data.job_id, state: "running", steps: [], stage: "starting", outcome: null, percent: 0, can_cancel: true, point_of_no_return: false, error: null, report: null, fs, label });
      setStage("running");
      return;
    }
    if (needsNewPlan(result.error.code) || result.error.code === "format_not_found") {
      setRefusal(result.error);
      setStage("refused");
    } else {
      notify(refusalText(result.error), "error");
    }
  };

  const cancel = async () => {
    if (!job) return;
    const result = await storageRequest<FormatJob>(`/format/jobs/${encodeKey(job.job_id)}`, { method: "DELETE" });
    if (result.ok) setJob(result.data);
    else notify(refusalText(result.error), "error");
  };

  const unregister = async (libraryKey: string) => {
    setBusy(true);
    const result = await storageRequest(`/volumes/${encodeKey(libraryKey)}/library?purge=true`, { method: "DELETE" });
    setBusy(false);
    if (!result.ok) {
      notify(storageErrorText(result.error, t, lang), "error");
      return;
    }
    onChanged();
    void loadPlan(windowsOrMac);
  };

  const close = () => {
    if (canLeaveWizard(job)) onClose();
  };

  let body: React.ReactNode = null;
  let footer: React.ReactNode;

  if (stage === "loading") {
    body = <div className="rl-center-note" role="status">{t("storage.format.loading")}</div>;
  } else if (stage === "refused" && refusal) {
    const actions = Array.isArray(refusal.extra.actions) ? (refusal.extra.actions as Array<{ id: string; key: string }>) : [];
    body = (
      <div className="dv-note dv-note--strong" role="alert">
        <Icon name="block" size={22} />
        <span>{refusalText(refusal)}</span>
      </div>
    );
    footer = (
      <div className="dv-actions">
        {actions.filter((a) => a.id === "unregister").slice(0, 1).map((a) => (
          <button key={a.key} type="button" className="btn btn-secondary" disabled={busy} onClick={() => unregister(a.key)}>{t("storage.format.unregister")}</button>
        ))}
        {(needsNewPlan(refusal.code) || refusal.code === "format_in_use" || refusal.code === "format_busy_operation") && (
          <button type="button" className="btn btn-secondary" onClick={() => void loadPlan(windowsOrMac)}>{t("storage.format.again")}</button>
        )}
        <button type="button" className="btn btn-secondary" onClick={onClose}>{t("storage.close")}</button>
      </div>
    );
  } else if (stage === "choose" && plan) {
    body = (
      <FormatChoose
        plan={plan} fs={fs} onChoose={choose} travels={windowsOrMac}
        onTravels={(checked) => { setWindowsOrMac(checked); void loadPlan(checked); }}
        label={label} onLabel={setLabel} labelIssue={labelIssue} labelMax={option?.label_max ?? 11} t={t} lang={lang}
      />
    );
    footer = (
      <div className="dv-actions">
        <button type="button" className="btn btn-secondary" onClick={onClose}>{t("storage.format.cancelWizard")}</button>
        <button type="button" className="btn btn-primary" disabled={!fs || !!labelIssue} onClick={toConfirm}>{t("storage.format.next")}</button>
      </div>
    );
  } else if (stage === "confirm" && plan && fs) {
    const ready = canConfirmFormat({ typed, expected: plan.confirm.expected, acknowledged, secondsLeft, labelOk: !labelIssue });
    body = (
      <FormatConfirm
        plan={plan} fs={fs} label={label} typed={typed} onTyped={setTyped}
        acknowledged={acknowledged} onAcknowledged={setAcknowledged} secondsLeft={secondsLeft} t={t}
      />
    );
    footer = (
      <div className="dv-actions">
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => setStage("choose")}>{t("storage.format.back")}</button>
        <button type="button" className="btn btn-danger" disabled={!ready || busy} onClick={execute}><Icon name="delete_forever" size={18} /> {t("storage.format.erase")}</button>
      </div>
    );
  } else if (stage === "running" || (stage === "result" && job)) {
    body = <FormatProgress job={job} running={stage === "running"} pollError={pollError} t={t} lang={lang} />;
    footer = stage === "running" ? (
      <div className="dv-actions">
        {job?.can_cancel && <button type="button" className="btn btn-secondary" onClick={cancel}>{t("storage.format.cancelJob")}</button>}
      </div>
    ) : (
      <div className="dv-actions"><button type="button" className="btn btn-primary" onClick={onClose}>{t("storage.format.done")}</button></div>
    );
  }

  return (
    <Sheet open onClose={close} title={t("storage.format.title", { name: target.name })} closeLabel={t("storage.close")} footer={footer} tall>
      {body}
    </Sheet>
  );
}
