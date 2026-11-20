export type UpdateStep =
  | "idle"
  | "checking"
  | "downloading"
  | "verifying"
  | "installing"
  | "restarting"
  | "awaiting_user_confirmation"
  | "done"
  | "failed";

export interface UpdateStatus {
  step: UpdateStep;
  percent: number | null;
  message: string | null;
  error: string | null;
  started_at: number | null;
  acknowledged_started_at: number | null;
}

type T = (key: string, params?: Record<string, string | number>) => string;

export const ACTIVE_STEPS: UpdateStep[] = [
  "checking", "downloading", "verifying", "installing", "restarting", "awaiting_user_confirmation",
];

export const STEPPER_STEPS: UpdateStep[] = ["checking", "downloading", "verifying", "installing", "restarting"];

export const STEP_LABEL_KEYS: Record<string, string> = {
  checking: "settingsPage.updateStepChecking",
  downloading: "settingsPage.updateStepDownloading",
  verifying: "settingsPage.updateStepVerifying",
  installing: "settingsPage.updateStepInstalling",
  restarting: "settingsPage.updateStepRestarting",
};

const PROGRESS_KEYS: Partial<Record<UpdateStep, string>> = {
  checking: "settingsPage.updateProgressChecking",
  verifying: "settingsPage.updateProgressVerifying",
  installing: "settingsPage.updateProgressInstalling",
  restarting: "settingsPage.updateProgressRestarting",
  awaiting_user_confirmation: "settingsPage.updateProgressAwaitingConfirmation",
  done: "settingsPage.updateProgressDone",
};

export function progressLabel(status: UpdateStatus, t: T): string {
  if (status.step === "downloading") return t("settingsPage.updateProgressDownloading", { percent: status.percent ?? 0 });
  if (status.step === "failed") return t("settingsPage.updateProgressFailed", { reason: status.error || status.message || "" });
  const key = PROGRESS_KEYS[status.step];
  return key ? t(key) : status.message || "";
}

export function isHidden(status: UpdateStatus | null): boolean {
  if (!status || status.step === "idle") return true;
  return status.started_at !== null && status.acknowledged_started_at === status.started_at;
}
