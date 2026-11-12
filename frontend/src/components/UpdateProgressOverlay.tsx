"use client";

import { useCallback, useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import { getApiUrl, getPlaybackWsUrl } from "@/lib/apiUrl";

type UpdateStep =
  | "idle"
  | "checking"
  | "downloading"
  | "verifying"
  | "installing"
  | "restarting"
  | "awaiting_user_confirmation"
  | "done"
  | "failed";

interface UpdateStatus {
  step: UpdateStep;
  percent: number | null;
  message: string | null;
  error: string | null;
  started_at: number | null;
  acknowledged_started_at: number | null;
}

const ACTIVE_STEPS: UpdateStep[] = [
  "checking", "downloading", "verifying", "installing", "restarting", "awaiting_user_confirmation",
];

const STEPPER_STEPS: UpdateStep[] = ["checking", "downloading", "verifying", "installing", "restarting"];

export default function UpdateProgressOverlay() {
  const { t } = useAppSettings();
  const [status, setStatus] = useState<UpdateStatus | null>(null);

  const applyStatus = useCallback((data: UpdateStatus | null | undefined) => {
    if (!data || !data.step) return;
    setStatus(data);
  }, []);

  const acknowledge = useCallback(() => {
    setStatus((prev) => (prev ? { ...prev, acknowledged_started_at: prev.started_at } : prev));
    fetch(getApiUrl("/updates/acknowledge"), { method: "POST" }).catch(() => {});
  }, []);

  useEffect(() => {
    fetch(getApiUrl("/updates/status"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then(applyStatus)
      .catch(() => {});
  }, [applyStatus]);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (cancelled || typeof window === "undefined") return;
      ws = new WebSocket(getPlaybackWsUrl());
      ws.onopen = () => ws?.send(JSON.stringify({ command: "subscribe", params: { channels: [] } }));
      ws.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data);
          if (parsed.event === "ping") {
            ws?.send(JSON.stringify({ command: "pong" }));
            return;
          }
          if (parsed.event === "update_progress") {
            applyStatus(parsed as UpdateStatus);
          }
        } catch {
        }
      };
      ws.onclose = () => {
        if (!cancelled) reconnectTimer = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [applyStatus]);

  if (!status || status.step === "idle") return null;
  if (status.started_at !== null && status.acknowledged_started_at === status.started_at) return null;

  const isActive = ACTIVE_STEPS.includes(status.step);
  const isFailed = status.step === "failed";
  const isDone = status.step === "done";

  const label = (() => {
    switch (status.step) {
      case "checking":
        return t("settingsPage.updateProgressChecking");
      case "downloading":
        return t("settingsPage.updateProgressDownloading", { percent: status.percent ?? 0 });
      case "verifying":
        return t("settingsPage.updateProgressVerifying");
      case "installing":
        return t("settingsPage.updateProgressInstalling");
      case "restarting":
        return t("settingsPage.updateProgressRestarting");
      case "awaiting_user_confirmation":
        return t("settingsPage.updateProgressAwaitingConfirmation");
      case "done":
        return t("settingsPage.updateProgressDone");
      case "failed":
        return t("settingsPage.updateProgressFailed", { reason: status.error || status.message || "" });
      default:
        return status.message || "";
    }
  })();

  const stepperIndex = STEPPER_STEPS.indexOf(status.step);
  const currentStepperIndex = isDone ? STEPPER_STEPS.length : stepperIndex;
  const showStepper = currentStepperIndex !== -1;
  const stepLabelKeys: Record<string, string> = {
    checking: "settingsPage.updateStepChecking",
    downloading: "settingsPage.updateStepDownloading",
    verifying: "settingsPage.updateStepVerifying",
    installing: "settingsPage.updateStepInstalling",
    restarting: "settingsPage.updateStepRestarting",
  };

  return (
    <div
      className={`toast ${isFailed ? "error" : isActive ? "warning" : ""}`}
      style={{ bottom: 24, left: 24, right: "auto", maxWidth: 420, flexDirection: "column", alignItems: "stretch", gap: 8 }}
      role="status"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Icon
          name={isFailed ? "error" : isDone ? "check_circle" : "system_update"}
          size={18}
          color={isFailed ? "var(--accent-error-text)" : isDone ? "var(--accent-success-text)" : "var(--accent-text)"}
        />
        <span style={{ flex: 1 }}>{label}</span>
        {(isDone || isFailed) && (
          <button
            type="button"
            onClick={acknowledge}
            aria-label={t("settingsPage.updateProgressDismiss")}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", display: "flex", alignItems: "center" }}
          >
            <Icon name="close" size={16} />
          </button>
        )}
      </div>
      {showStepper && (
        <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
          {STEPPER_STEPS.map((step, i) => {
            const stepState = i < currentStepperIndex ? "done" : i === currentStepperIndex ? "active" : "pending";
            return (
              <div key={step} style={{ display: "flex", alignItems: "center", flex: i < STEPPER_STEPS.length - 1 ? 1 : "0 0 auto" }}>
                <div
                  title={t(stepLabelKeys[step])}
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    background: stepState === "pending" ? "transparent" : "var(--accent-primary)",
                    border: `2px solid ${stepState === "pending" ? "var(--border-color)" : "var(--accent-text)"}`,
                  }}
                >
                  {stepState === "done" && <Icon name="check" size={10} color="var(--accent-primary-fg)" />}
                  {stepState === "active" && (
                    <div style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent-primary-fg)" }} />
                  )}
                </div>
                {i < STEPPER_STEPS.length - 1 && (
                  <div
                    style={{
                      flex: 1,
                      height: 2,
                      background: i < currentStepperIndex ? "var(--accent-primary)" : "var(--border-color)",
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
      {status.step === "downloading" && (
        <div style={{ height: 4, borderRadius: 2, background: "var(--border-color)", overflow: "hidden" }}>
          <div
            style={{
              height: "100%",
              width: `${status.percent ?? 0}%`,
              background: "var(--accent-primary)",
              transition: "width 0.3s ease",
            }}
          />
        </div>
      )}
    </div>
  );
}
