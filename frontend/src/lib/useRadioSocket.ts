"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clearCachesAndReload } from "@/lib/cacheReload";
import type { ClockAnchor } from "@/lib/playbackClock";
import { ServerClockSync } from "@/lib/serverClockSync";
import type { DisplayOutput, RadioChannelId } from "@/lib/displayChannel";
import { defaultSound, type RadioSoundSettings } from "@/lib/radioSound";
import type { ClockTarget } from "@/lib/useMediaClockFollower";

/** État d'UNE sortie radio (`radio_cable` ou `radio_network`) : un moteur INDÉPENDANT par
 * sortie, distinct du câblé/réseau vidéo (RadioPlaybackManager côté backend).
 * Partage la même connexion WebSocket `/ws/playback` que usePlaybackSocket
 * (filtrée sur le `channel` de la sortie), mais un vocabulaire d'état et de
 * commandes propre — pas de vidéo/cours, une playlist de morceaux. */

export interface RadioTrackInfo {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
  /** Style musical (étiquette libre de la bibliothèque), absent d'un ancien état serveur. */
  genre?: string | null;
  duration_seconds: number | null;
  cover_url: string | null;
}

export type RadioRepeatMode = "off" | "playlist" | "track";

/** Rappel en cours : "wait_end" = inséré entre 2 pistes
 * (musique déjà arrêtée), "duck" = fondu immédiat pendant que la musique
 * continue (X min / heures fixes / manuel). */
export interface RadioAnnouncementInfo {
  id: number;
  description: string;
  mode: "wait_end" | "duck";
}

export interface RadioState {
  state: "idle" | "playing" | "paused" | "announcing";
  playlist_id: number | null;
  playlist_name: string | null;
  order: RadioTrackInfo[];
  index: number | null;
  current_track: RadioTrackInfo | null;
  position_seconds: number;
  duration_seconds: number | null;
  /** Ancre de l'horloge de lecture pilotée par le serveur. */
  clock?: ClockAnchor | null;
  volume: number;
  shuffle: boolean;
  repeat: RadioRepeatMode;
  playing: boolean;
  crossfade_seconds: number;
  current_announcement: RadioAnnouncementInfo | null;
  tracks_since_announcement: number;
  /** Réglages de son de la sortie (égaliseur, basses…), appliqués par le lecteur. */
  sound: RadioSoundSettings;
}

const DEFAULT_STATE: RadioState = {
  state: "idle",
  playlist_id: null,
  playlist_name: null,
  order: [],
  index: null,
  current_track: null,
  position_seconds: 0,
  duration_seconds: null,
  volume: 100,
  shuffle: false,
  repeat: "off",
  playing: false,
  crossfade_seconds: 4,
  current_announcement: null,
  tracks_since_announcement: 0,
  sound: defaultSound(),
  clock: null,
};

/** Cible du suiveur d'horloge pour le lecteur /radio : la piste courante, en lecture ou en
 * pause. Aucun suivi pendant un rappel (état « announcing ») : la musique y est gérée par
 * le rappel (fondu, attente de fin). */
export function selectRadioTarget(state: RadioState): ClockTarget {
  if (!state.current_track || (state.state !== "playing" && state.state !== "paused")) {
    return { anchor: null, mode: null };
  }
  return { anchor: state.clock, mode: state.playing ? "playing" : "paused", key: state.current_track.id };
}

export interface RadioEvent {
  event: "state_change";
  cause: string;
  channel: RadioChannelId;
  data: RadioState;
  client_ts?: number;
}

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const isDevServer = window.location.port === "3000";
  const host = isDevServer ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}

function getApiUrl(path: string): string {
  if (typeof window === "undefined") return "";
  const isDevServer = window.location.port === "3000";
  return isDevServer ? `http://localhost:8001/api${path}` : `/api${path}`;
}

// Même filet de sécurité que usePlaybackSocket : recale l'état sur GET /api/radio/state à
// intervalle régulier, au cas où un broadcast() aurait été perdu.
const RESYNC_INTERVAL_MS = 15000;

/**
 * @param onEvent  Callback appelé à chaque changement d'état reçu.
 * @param channel  Sortie radio suivie : `radio_network` par défaut (ancien poste radio unique),
 *                 `radio_cable` pour la sortie câblée. Chaque sortie a son propre moteur,
 *                 son rôle primaire et ses évènements.
 * @param role     "kiosk" pour le poste /radio : envoie un identify
 *                 à la connexion et reçoit son statut primaire/miroir en
 *                 retour — seul le primaire a autorité pour rapporter
 *                 la position réelle de lecture. Omis pour une télécommande
 *                 (radio-remote), qui ne fait que refléter/commander l'état.
 */
export function useRadioSocket(
  onEvent?: (evt: RadioEvent) => void,
  role?: "kiosk",
  channel: RadioChannelId = "radio_network",
) {
  const [state, setState] = useState<RadioState>(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  const [isPrimary, setIsPrimary] = useState(false);
  // Sortie affichée par l'écran CÂBLÉ (kiosk, cinéma ou radio) : null tant que la valeur
  // initiale n'est pas chargée. Seule la radio câblée la suit, pour repartir vers kiosk/cinéma
  // quand l'admin y rebascule l'écran câblé (cf. useDisplayOutputRedirect).
  const [displayOutputCable, setDisplayOutputCable] = useState<DisplayOutput | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingCommandsRef = useRef<{ payload: string; queuedAt: number }[]>([]);
  const onEventRef = useRef(onEvent);
  const stateRef = useRef<RadioState>(DEFAULT_STATE);
  // Détection d'un backend redémarré depuis le chargement de CETTE page — même
  // patron que usePlaybackSocket.ts : null jusqu'au premier "boot_id" reçu
  // (référence pour cette page), une valeur différente à une reconnexion
  // ultérieure signale un redémarrage backend entre-temps.
  const bootIdRef = useRef<string | null>(null);
  // Mesure du décalage d'horloge avec le serveur (partagée avec usePlaybackSocket).
  const clockSyncRef = useRef(new ServerClockSync());

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let retryDelay = 1000;
    const MAX_RETRY_DELAY = 30000;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        setConnected(true);
        retryDelay = 1000;
        // Identification du rôle kiosk : envoyée dès
        // l'ouverture pour que le backend assigne le rôle primaire/miroir
        // avant tout report_position.
        // Abonnement de canal : n'écoute que les évènements radio.
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: [channel] } }));
        clockSyncRef.current.start(ws, () => wsRef.current === ws);
        if (role === "kiosk") {
          ws.send(JSON.stringify({ command: "identify", params: { role: "kiosk", channel } }));
        }
        const now = Date.now();
        const pending = pendingCommandsRef.current.filter((p) => now - p.queuedAt < 5000);
        pendingCommandsRef.current = [];
        for (const p of pending) ws.send(p.payload);
      };

      ws.onmessage = (evt) => {
        if (wsRef.current !== ws) return;
        try {
          const parsed = JSON.parse(evt.data);
          if (parsed.event === "ping") {
            ws.send(JSON.stringify({ command: "pong" }));
            return;
          }
          if (clockSyncRef.current.handleMessage(parsed)) return;
          if (parsed.event === "boot_id") {
            if (bootIdRef.current === null) {
              bootIdRef.current = parsed.boot_id;
            } else if (bootIdRef.current !== parsed.boot_id) {
              void clearCachesAndReload();
            }
            return;
          }
          if (parsed.event === "kiosk_role") {
            setIsPrimary(!!parsed.is_primary);
            return;
          }
          if (parsed.event === "promoted_primary") {
            setIsPrimary(true);
            return;
          }
          if (parsed.event === "display_output") {
            if (
              parsed.channel === "cable" &&
              (parsed.output === "kiosk" || parsed.output === "cinema" || parsed.output === "radio")
            ) {
              setDisplayOutputCable(parsed.output);
            }
            return;
          }
          // Autres évènements d'autres canaux de diffusion (cinema_*...) : sans objet ici, ignorés.
          if (parsed.event === "force_reload") {
            // Cf. usePlaybackSocket : vide les caches puis recharge (bouton
            // « Synchronisation des écrans » — nouveaux assets re-téléchargés).
            void clearCachesAndReload();
            return;
          }
          if (parsed.event === "state_change" && parsed.channel === channel) {
            setState(parsed.data);
            onEventRef.current?.(parsed as RadioEvent);
          }
        } catch (err) {
          console.error("Message WebSocket radio invalide", err);
        }
      };

      ws.onclose = () => {
        clockSyncRef.current.stop();
        if (wsRef.current !== ws) return;
        setConnected(false);
        setIsPrimary(false);
        wsRef.current = null;
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [role, channel]);

  useEffect(() => {
    let cancelled = false;
    const resync = () => {
      fetch(getApiUrl(`/radio/state?channel=${channel}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data: RadioState | null) => {
          if (cancelled || !data) return;
          if (JSON.stringify(stateRef.current) === JSON.stringify(data)) return;
          setState(data);
          onEventRef.current?.({ event: "state_change", cause: "sync", channel, data });
        })
        .catch(() => {});
    };
    const id = setInterval(resync, RESYNC_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [channel]);

  // Valeur initiale de la sortie câblée ; les changements suivants arrivent par `display_output`.
  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl("/settings/display-output"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        if (data.cable === "kiosk" || data.cable === "cinema" || data.cable === "radio") {
          setDisplayOutputCable((prev) => prev ?? data.cable);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const sendCommand = useCallback((command: string, params: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    const payload = JSON.stringify({
      command,
      params: { channel, ...params, client_ts: Date.now() },
    });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
      return;
    }
    pendingCommandsRef.current.push({ payload, queuedAt: Date.now() });
    if (pendingCommandsRef.current.length > 10) pendingCommandsRef.current.shift();
  }, [channel]);

  const serverNow = useCallback(() => clockSyncRef.current.serverNow(), []);

  return { state, connected, sendCommand, isPrimary, serverNow, displayOutputCable };
}
