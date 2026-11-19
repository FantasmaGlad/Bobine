"use client";

import Sheet from "@/components/Sheet";import { canLeaveWizard, labelProblem, type FormatJob, type FormatOption } from "@/lib/storage/format";
import { encodeKey, storageRequest } from "@/lib/storage/request";
import { storageErrorText, type StorageCtx } from "./common";
import { renderStage } from "./format/stages";
import { useConfirmClock } from "./format/useConfirmClock";
import { useFormatActions } from "./format/useFormatActions";
import { useFormatPlan } from "./format/useFormatPlan";

interface Props extends StorageCtx {
  target: { key: string; name: string; resume?: FormatJob | null } | null;
  onClose: () => void;
  onChanged: () => void;
}

export default function FormatWizard({ target, onClose, onChanged, t, lang, notify }: Props) {
  if (!target) return <Sheet open={false} onClose={onClose}>{null}</Sheet>;
  return <WizardBody key={target.key + (target.resume?.job_id ?? "")} target={target} onClose={onClose} onChanged={onChanged} t={t} lang={lang} notify={notify} />;
}

function WizardBody({ target, onClose, onChanged, t, lang, notify }: Props & { target: NonNullable<Props["target"]> }) {
  const ctx = { t, lang, notify };
  const plan = useFormatPlan(target.key, !!target.resume);
  const clock = useConfirmClock(plan.stage, plan.setStage);
  const actions = useFormatActions({
    targetKey: target.key, resume: target.resume, stage: plan.stage, setStage: plan.setStage, setRefusal: plan.setRefusal,
    plan: plan.plan, fs: plan.fs, label: plan.label, typed: clock.typed, acknowledged: clock.acknowledged, ctx, onChanged,
  });
  const option: FormatOption | undefined = plan.plan?.options.find((o) => o.fs === plan.fs);
  const labelIssue = plan.fs ? labelProblem(plan.fs, plan.label) : "empty";

  const choose = (next: FormatOption) => {
    if (!next.available) return;
    plan.setFs(next.fs);
    plan.setLabel(next.label);
  };

  const unregister = async (libraryKey: string) => {
    actions.setBusy(true);
    const result = await storageRequest(`/volumes/${encodeKey(libraryKey)}/library?purge=true`, { method: "DELETE" });
    actions.setBusy(false);
    if (!result.ok) {
      notify(storageErrorText(result.error, t, lang), "error");
      return;
    }
    onChanged();
    void plan.loadPlan(plan.windowsOrMac);
  };

  const close = () => {
    if (canLeaveWizard(actions.job)) onClose();
  };
  const { body, footer } = renderStage({ ctx, plan, clock, actions, labelIssue, option, choose, unregister, onClose });

  return (
    <Sheet open onClose={close} title={t("storage.format.title", { name: target.name })} closeLabel={t("storage.close")} footer={footer} tall>
      {body}
    </Sheet>
  );
}
