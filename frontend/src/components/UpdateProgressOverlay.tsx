"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";

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
}

const ACTIVE_STEPS: UpdateStep[] = [
  "checking", "downloading", "verifying", "installing", "restarting", "awaiting_user_confirmation",
];

function getApiUrl(path: string): string {
  if (typeof window === "undefined") return "";
  const isDevServer = window.location.port === "3000";
  return isDevServer ? `http://localhost:8001/api${path}` : `/api${path}`;
}

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const isDevServer = window.location.port === "3000";
  const host = isDevServer ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}

/**
 * Bannière de progression de mise à jour, montée globalement (cf.
 * ClientLayout) — remplace l'ancien comportement où le bouton "Mettre à
 * jour" de Réglages affichait un succès dès que le téléchargement était
 * seulement PLANIFIÉ côté serveur (cf. rapport de santé, constat
 * prioritaire n°1). Reste utile même en dehors de Réglages : une mise à
 * jour PLANIFIÉE (Réglages → Mise à jour automatique, déclenchée sans
 * qu'aucun onglet ne soit ouvert sur cette page) doit rester visible à
 * quiconque a un écran Bobine ouvert au moment où elle se termine.
 *
 * Connexion WebSocket minimale et passive sur le canal déjà partagé par le
 * reste de l'app (`/ws/playback`), même patron que la synchronisation
 * temps réel de AppSettingsContext — pas de connexion dédiée
 * supplémentaire, aucune commande jamais envoyée.
 */
export default function UpdateProgressOverlay() {
  const { t } = useAppSettings();
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const lastStartedAtRef = useRef<number | null>(null);

  const applyStatus = useCallback((data: UpdateStatus | null | undefined) => {
    if (!data || !data.step) return;
    if (data.started_at !== lastStartedAtRef.current) {
      // Nouvelle exécution du pipeline : une bannière "terminé"/"échoué"
      // précédemment fermée par l'utilisateur doit pouvoir réapparaître.
      lastStartedAtRef.current = data.started_at;
      setDismissed(null);
    }
    setStatus(data);
  }, []);

  // État initial au montage (page rechargée pile après un redémarrage
  // déclenché par la mise à jour elle-même, ou WebSocket pas encore
  // connecté) — sans ce fetch, la seule source serait l'évènement
  // WebSocket suivant, qui peut arriver bien après la fin réelle.
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
      ws = new WebSocket(getWsUrl());
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
          // Message illisible : sans conséquence, le prochain évènement suffira.
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
  if (dismissed === String(status.started_at)) return null;

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
          color={isFailed ? "var(--accent-error)" : isDone ? "var(--accent-success)" : "var(--accent-primary)"}
        />
        <span style={{ flex: 1 }}>{label}</span>
        {(isDone || isFailed) && (
          <button
            type="button"
            onClick={() => setDismissed(String(status.started_at))}
            aria-label={t("settingsPage.updateProgressDismiss")}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", display: "flex", alignItems: "center" }}
          >
            <Icon name="close" size={16} />
          </button>
        )}
      </div>
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
