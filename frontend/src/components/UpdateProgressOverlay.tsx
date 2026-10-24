"use client";

import { useCallback, useEffect, useState } from "react";
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
  acknowledged_started_at: number | null;
}

const ACTIVE_STEPS: UpdateStep[] = [
  "checking", "downloading", "verifying", "installing", "restarting", "awaiting_user_confirmation",
];

// Sous-ensemble d'ACTIVE_STEPS affiché comme un mini-stepper façon
// "installeur wizard" (fait / en cours / à venir) — "awaiting_user_
// confirmation" (spécifique Android : attente d'un tap sur l'appareil, pas
// une étape séquentielle du pipeline) garde son affichage textuel seul,
// sans entrer dans cette séquence linéaire.
const STEPPER_STEPS: UpdateStep[] = ["checking", "downloading", "verifying", "installing", "restarting"];

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

  const applyStatus = useCallback((data: UpdateStatus | null | undefined) => {
    if (!data || !data.step) return;
    setStatus(data);
  }, []);

  // Acquittement persisté côté SERVEUR (`POST /api/updates/acknowledge`),
  // pas un state React local : un ancien `dismissed` purement côté client
  // revenait à `null` à chaque rechargement de page ou redémarrage de
  // service déclenché par la mise à jour elle-même, faisant réapparaître la
  // notification "en boucle" malgré sa fermeture (cause racine confirmée).
  // Mise à jour optimiste du state local pour une fermeture instantanée,
  // sans attendre l'aller-retour réseau ni l'écho WebSocket.
  const acknowledge = useCallback(() => {
    setStatus((prev) => (prev ? { ...prev, acknowledged_started_at: prev.started_at } : prev));
    fetch(getApiUrl("/updates/acknowledge"), { method: "POST" }).catch(() => {});
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
      // N'écoute que les évènements globaux : aucun canal.
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

  // Mini-stepper "installeur wizard" : chaque étape passée affiche une coche SVG,
  // l'étape en cours un point plein, les suivantes un cercle vide — répond
  // au constat "pas assez d'informations visuelles sur ce qu'il se passe
  // pendant l'installation d'une mise à jour". Affiché pendant les étapes
  // séquentielles actives, et entièrement coché une fois "done" (pour que
  // la bannière de succès ne retombe pas brutalement à un simple texte nu).
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
          color={isFailed ? "var(--accent-error)" : isDone ? "var(--accent-success)" : "var(--accent-primary)"}
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
                    border: `2px solid ${stepState === "pending" ? "var(--border-color)" : "var(--accent-primary)"}`,
                  }}
                >
                  {stepState === "done" && <Icon name="check" size={10} color="#fff" />}
                  {stepState === "active" && (
                    <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#fff" }} />
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
