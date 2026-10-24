"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import {
  canConfirmFormat, canLeaveWizard, defaultFormat, encodeKey, formatBytes, formatFinished, formatTravels, fsLabel, labelProblem, needsNewPlan,
  reflectionLeft, refusalKey, stepIcon, storageRequest, visibleNotes, FORMAT_STEP_ORDER,
  type FormatFs, type FormatJob, type FormatOption, type FormatPlan,
} from "@/lib/storageApi";
import type { ApiError } from "@/lib/devicesApi";
import { storageErrorText, tr, type StorageCtx } from "./common";

interface Props extends StorageCtx {
  /** Support à préparer (clé et nom) ; `resume` reprend une opération déjà en cours (page rechargée). */
  target: { key: string; name: string; resume?: FormatJob | null } | null;
  onClose: () => void;
  onChanged: () => void;
}

type Stage = "loading" | "refused" | "choose" | "confirm" | "running" | "result";

const POLL_MS = 700;
const REFLECTION_SECONDS = 5;

/** Parcours guidé « Préparer ce support » : vérification, choix du format, confirmation forte, déroulement, rapport. */
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
  const [pin, setPin] = useState("");
  const [pinError, setPinError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState(0);
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const [pollError, setPollError] = useState(false);
  const [job, setJob] = useState<FormatJob | null>(target.resume ?? null);
  const finished = useRef(false);
  const changed = useRef(onChanged);
  useEffect(() => {
    changed.current = onChanged;
  }, [onChanged]);

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

  // Suivi de l'opération : relecture régulière de l'état du travail jusqu'à sa fin.
  useEffect(() => {
    if (stage !== "running" || !job) return;
    const jobId = job.job_id;
    const timer = setInterval(async () => {
      const result = await storageRequest<FormatJob>(`/format/jobs/${encodeKey(jobId)}`);
      if (!result.ok) {
        setPollError(true);
        if (result.error.status === 404) {
          setJob({ ...job, state: "failed", outcome: "unverified", can_cancel: false, error: { code: "format_job_not_found", message: "" } });
          setStage("result");
        }
        return;
      }
      setPollError(false);
      setJob(result.data);
      if (formatFinished(result.data) && !finished.current) {
        finished.current = true;
        setStage("result");
        changed.current();
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [stage, job]);

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
    setPin("");
    setPinError(null);
    const start = Date.now();
    setStartedAt(start);
    setNow(start);
    setStage("confirm");
  };

  const execute = async () => {
    if (!plan || !fs) return;
    setBusy(true);
    setPinError(null);
    const result = await storageRequest<{ job_id: string }>("/format/execute", {
      body: { key: target.key, token: plan.token, fs, label: label.trim(), confirm: typed, acknowledged, pin: plan.pin_required ? pin : undefined },
    });
    setBusy(false);
    if (result.ok) {
      finished.current = false;
      const first = await storageRequest<FormatJob>(`/format/jobs/${encodeKey(result.data.job_id)}`);
      setJob(first.ok ? first.data : { job_id: result.data.job_id, state: "running", steps: [], stage: "starting", outcome: null, percent: 0, can_cancel: true, point_of_no_return: false, error: null, report: null, fs, label });
      setStage("running");
      return;
    }
    if (result.error.code === "format_pin_required" || result.error.code === "format_pin_invalid" || result.error.code === "locked") {
      setPinError(refusalText(result.error));
    } else if (needsNewPlan(result.error.code) || result.error.code === "format_not_found") {
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

  // ---------------------------------------------------------------- rendu par étape
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
    const volume = plan.content.volumes[0];
    const media = plan.content.volumes.reduce((acc, v) => ({ video: acc.video + (v.media?.video ?? 0), audio: acc.audio + (v.media?.audio ?? 0) }), { video: 0, audio: 0 });
    const roots = plan.content.volumes.flatMap((v) => v.root ?? []).slice(0, 8).map((e) => e.name).join(", ");
    body = (
      <div className="dv-detail">
        <div className="fmt-erase" role="note">
          <strong>{t("storage.format.warning")}</strong>
          <span className="dv-sub">{t("storage.format.erasesLine", { partitions: plan.erases.partitions, files: plan.erases.files })}</span>
          {volume?.readable !== false && plan.erases.files > 0 && (
            <span className="dv-sub">
              {plan.erases.truncated ? t("storage.format.filesMore", { files: plan.erases.files }) : t("storage.format.filesLine", { files: plan.erases.files, dirs: plan.content.volumes.reduce((n, v) => n + (v.dirs ?? 0), 0) })}
              {(media.video || media.audio) ? ` · ${t("storage.format.mediaLine", { videos: media.video, tracks: media.audio })}` : ""}
            </span>
          )}
          {roots && <span className="dv-sub">{t("storage.format.rootLine", { names: roots })}</span>}
          {plan.erases.unreadable && <span className="dv-sub">{t("storage.format.unreadable")}</span>}
        </div>
        <div className="dv-detail-block">
          <div className="dv-row">
            <span className="dv-icon"><Icon name="usb" size={22} /></span>
            <span className="dv-text">
              <span className="dv-title">{plan.target.name}</span>
              <span className="dv-sub">
                {t("storage.format.currentLine", {
                  fs: plan.target.partitions.map((p) => fsLabel(p.fstype)).join(" + ") || "—",
                  used: formatBytes(plan.content.bytes_used, lang),
                  size: formatBytes(plan.target.size_bytes, lang),
                })}
              </span>
            </span>
          </div>
        </div>
        <label className="st-check st-check--chip">
          <input type="checkbox" checked={windowsOrMac} onChange={(e) => { setWindowsOrMac(e.target.checked); void loadPlan(e.target.checked); }} />
          <span>{t("storage.format.travels")}</span>
        </label>
        <div className="dv-detail-block">
          <h4>{t("storage.format.formatTitle")}</h4>
          <div className="fmt-options" role="radiogroup" aria-label={t("storage.format.formatTitle")}>
            {plan.options.map((o) => {
              const notes = visibleNotes({ reason: o.reason, notes: o.notes.filter((n) => n !== "quick_format_only") }, 3);
              return (
                <label key={o.fs} className="fmt-option glass-interactive" aria-disabled={!o.available}>
                  <input type="radio" name="fmt-fs" checked={fs === o.fs} disabled={!o.available} onChange={() => choose(o)} />
                  <span className="dv-text">
                    <span className="dv-title">
                      {fsLabel(o.fs)}
                      {o.recommended && <span className="dv-badge">{t("storage.format.recommended")}</span>}
                    </span>
                    <span className="dv-sub">{o.available ? `${t(`storage.verdict.${o.verdict}`)} · ${tr(t, `storage.fsReasons.${o.reason}`)}` : tr(t, `storage.format.unavailable.${o.unavailable}`, "", { package: o.install_package ?? "" })}</span>
                    {o.available && notes.length > 0 && <span className="dv-sub">{notes.map((n) => tr(t, `storage.fsNotes.${n}`)).filter(Boolean).join(" · ")}</span>}
                    {o.available && o.fs === "exfat" && o.cluster_bytes && <span className="dv-sub">{t("storage.format.cluster", { size: formatBytes(o.cluster_bytes, lang) })}</span>}
                  </span>
                </label>
              );
            })}
          </div>
          <p className="dv-sub"><Icon name="info" size={14} /> {t("storage.fsNotes.quick_format_only")}</p>
        </div>
        <div className="fmt-field">
          <label htmlFor="fmt-label" className="dv-title">{t("storage.format.labelTitle")}</label>
          <input id="fmt-label" className="form-control" value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} aria-invalid={!!labelIssue} autoComplete="off" />
          <span className={labelIssue ? "dv-error" : "dv-sub"}>
            {labelIssue ? t(`storage.format.labelProblem.${labelIssue}`) : t("storage.format.labelHint", { max: option?.label_max ?? 11 })}
          </span>
        </div>
      </div>
    );
    footer = (
      <div className="dv-actions">
        <button type="button" className="btn btn-secondary" onClick={onClose}>{t("storage.format.cancelWizard")}</button>
        <button type="button" className="btn btn-primary" disabled={!fs || !!labelIssue} onClick={toConfirm}>{t("storage.format.next")}</button>
      </div>
    );
  } else if (stage === "confirm" && plan && fs) {
    const ready = canConfirmFormat({ typed, expected: plan.confirm.expected, acknowledged, secondsLeft, pinRequired: plan.pin_required, pin, labelOk: !labelIssue });
    body = (
      <div className="dv-detail">
        <div className="fmt-erase" role="alert">
          <strong>{t("storage.format.summary", { name: plan.target.name, fs: fsLabel(fs), label: label.trim() })}</strong>
          <span className="dv-sub">{t("storage.format.warning")}</span>
        </div>
        <div className="fmt-field">
          <label htmlFor="fmt-confirm" className="dv-title">{t(`storage.format.confirmMode.${plan.confirm.mode}`, { value: plan.confirm.expected })}</label>
          <input id="fmt-confirm" className="form-control" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" autoCapitalize="off" spellCheck={false} />
        </div>
        <label className="st-check st-check--chip">
          <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
          <span>{t("storage.format.ack")}</span>
        </label>
        {plan.pin_required && (
          <div className="fmt-field">
            <label htmlFor="fmt-pin" className="dv-title">{t("storage.format.pin")}</label>
            <input id="fmt-pin" className="form-control dv-pin-input" inputMode="numeric" type="password" maxLength={6} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} autoComplete="off" />
            {pinError && <span className="dv-error" role="alert">{pinError}</span>}
          </div>
        )}
        {secondsLeft > 0 && <p className="dv-sub fmt-count" role="status">{t("storage.format.wait", { count: secondsLeft })}</p>}
      </div>
    );
    footer = (
      <div className="dv-actions">
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => setStage("choose")}>{t("storage.format.back")}</button>
        <button type="button" className="btn btn-danger" disabled={!ready || busy} onClick={execute}><Icon name="delete_forever" size={18} /> {t("storage.format.erase")}</button>
      </div>
    );
  } else if (stage === "running" || (stage === "result" && job)) {
    const steps = job?.steps ?? FORMAT_STEP_ORDER.map((id) => ({ id, state: "pending" as const }));
    const report = job?.report;
    const outcome = job?.outcome;
    body = (
      <div className="dv-detail">
        {stage === "running" && pollError && <p className="dv-error" role="status">{t("storage.format.connectionLost")}</p>}
        {stage === "running" && (
          <div className="dv-note dv-note--strong" role="status">
            <Icon name={job?.point_of_no_return ? "lock" : "pending"} size={20} />
            <span>{job?.point_of_no_return ? t("storage.format.noReturn") : t("storage.format.canCancel")}</span>
          </div>
        )}
        {stage === "result" && outcome && (
          <div className={outcome === "verified" ? "dv-note dv-note--strong" : "fmt-erase"} role="status">
            <strong>{t(`storage.format.outcomeTitle.${outcome}`)}</strong>
            <span className="dv-sub">{t(`storage.format.outcomeText.${outcome}`)}</span>
            {job?.error && <span className="dv-sub">{tr(t, refusalKey(job.error.code), job.error.message)}</span>}
          </div>
        )}
        <ul className="fmt-steps" aria-label={t("storage.format.stepsTitle")}>
          {steps.map((s) => (
            <li key={s.id} data-state={s.state}>
              <Icon name={stepIcon(s.state)} size={20} />
              <span>{t(`storage.format.steps.${s.id}`)}</span>
            </li>
          ))}
        </ul>
        {stage === "result" && report && (report.checks?.length ?? 0) > 0 && (
          <div className="dv-detail-block">
            <div className="fmt-checks">
              {report.checks?.map((c) => (
                <span key={c.id} className="fmt-chip" data-ok={c.ok}><Icon name={c.ok ? "check_circle" : "error"} size={16} />{tr(t, `storage.format.checks.${c.id}`, c.id)}</span>
              ))}
            </div>
            {report.size_bytes != null && <p className="dv-sub">{t("storage.format.resultLine", { fs: fsLabel(report.filesystem), label: report.label ?? "", size: formatBytes(report.size_bytes, lang) })}</p>}
            <p className="dv-sub">{report.health?.available ? t(`storage.format.health.${report.health.status === "ok" ? "ok" : "warn"}`) : t("storage.format.health.unknown")}</p>
            {report.mounted_read_only && <p className="dv-sub">{t("storage.format.readOnlyNote")}</p>}
          </div>
        )}
      </div>
    );
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
