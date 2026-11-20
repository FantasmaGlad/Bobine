import Icon from "@/components/Icon";
import { ACTIVE_STEPS, progressLabel, STEPPER_STEPS, type UpdateStatus } from "./updateStatus";
import UpdateStepper from "./UpdateStepper";

type T = (key: string, params?: Record<string, string | number>) => string;

function toastIcon(isFailed: boolean, isDone: boolean) {
  if (isFailed) return { name: "error", color: "var(--accent-error-text)" };
  if (isDone) return { name: "check_circle", color: "var(--accent-success-text)" };
  return { name: "system_update", color: "var(--accent-text)" };
}

function DownloadBar({ percent }: { percent: number | null }) {
  return (
    <div style={{ height: 4, borderRadius: 2, background: "var(--border-color)", overflow: "hidden" }}>
      <div
        style={{
          height: "100%",
          width: `${percent ?? 0}%`,
          background: "var(--accent-primary)",
          transition: "width 0.3s ease",
        }}
      />
    </div>
  );
}

export default function UpdateToast({ status, t, onDismiss }: { status: UpdateStatus; t: T; onDismiss: () => void }) {
  const isActive = ACTIVE_STEPS.includes(status.step);
  const isFailed = status.step === "failed";
  const isDone = status.step === "done";
  const current = isDone ? STEPPER_STEPS.length : STEPPER_STEPS.indexOf(status.step);
  const icon = toastIcon(isFailed, isDone);
  return (
    <div
      className={`toast ${isFailed ? "error" : isActive ? "warning" : ""}`}
      style={{ bottom: 24, left: 24, right: "auto", maxWidth: 420, flexDirection: "column", alignItems: "stretch", gap: 8 }}
      role="status"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Icon name={icon.name} size={18} color={icon.color} />
        <span style={{ flex: 1 }}>{progressLabel(status, t)}</span>
        {(isDone || isFailed) && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label={t("settingsPage.updateProgressDismiss")}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", display: "flex", alignItems: "center" }}
          >
            <Icon name="close" size={16} />
          </button>
        )}
      </div>
      {current !== -1 && <UpdateStepper current={current} t={t} />}
      {status.step === "downloading" && <DownloadBar percent={status.percent} />}
    </div>
  );
}
