"use client";

import { useEffect, useRef } from "react";
import type { PlaybackState } from "@/lib/usePlaybackSocket";
import { anchorPosition, msUntilStart, planDrift } from "@/lib/playbackClock";

// Cadence de la boucle de suivi : assez courte pour tenir une précision de
// l'ordre de 100 ms, assez longue pour ne rien coûter (comparaison de deux
// nombres, aucun re-rendu React).
const FOLLOW_INTERVAL_MS = 200;
// Au-delà de cet écart (s) à l'arrêt/avant le départ, on replace le média.
const HOLD_SEEK_THRESHOLD_S = 0.25;
// Après un `seek`, on laisse le décodeur se stabiliser avant de juger la dérive,
// et on n'en refait pas un autre tout de suite (anti-boucle).
const SETTLE_AFTER_SEEK_MS = 1500;
const MIN_MS_BETWEEN_SEEKS = 4000;
// Latence moyenne d'un seek (s) compensée en visant légèrement devant.
const SEEK_LATENCY_COMPENSATION_S = 0.2;
// Fenêtre dans laquelle on arme le minuteur précis de démarrage synchronisé.
const START_ARM_WINDOW_MS = 600;

interface Options {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  state: PlaybackState;
  /** Heure serveur estimée (epoch, ms). */
  serverNow: () => number;
  /** Lance la lecture avec le repli d'autoplay propre à la page. */
  tryPlay: (el: HTMLMediaElement | null | undefined) => void;
  /** Notifie qu'un `seek` vient d'être émis (chiens de garde de la page). */
  onSeek?: () => void;
}

/**
 * Fait suivre au <video> d'un écran l'horloge de lecture publiée par le
 * serveur (réf. plan 4.0, P2-4) :
 *  - avant l'instant de départ : maintenu en pause à la bonne position
 *    (préchargé), puis `play()` lancé à l'instant exact -> tous les écrans
 *    démarrent ensemble ;
 *  - en lecture : dérive mesurée en continu et corrigée par un ajustement de
 *    `playbackRate` (±5 %), SANS `seek` ; un seul `seek` au-delà de 2 s ;
 *  - en pause : maintenu en pause à la position de l'ancre.
 * Ne touche jamais à un média en cours de chargement ou de seek.
 */
export function useVideoClockFollower({ videoRef, state, serverNow, tryPlay, onSeek }: Options) {
  const stateRef = useRef(state);
  const serverNowRef = useRef(serverNow);
  const tryPlayRef = useRef(tryPlay);
  const onSeekRef = useRef(onSeek);
  useEffect(() => {
    stateRef.current = state;
    serverNowRef.current = serverNow;
    tryPlayRef.current = tryPlay;
    onSeekRef.current = onSeek;
  });

  useEffect(() => {
    let correcting = false;
    let lastSeekAt = 0;
    let lastPlayAttemptAt = 0;
    let startTimer: ReturnType<typeof setTimeout> | null = null;

    // Relance de lecture limitée à 1/s : un autoplay refusé par le navigateur
    // ne doit pas être retenté (et son repli muet re-déclenché) toutes les 200 ms.
    const playThrottled = (video: HTMLVideoElement) => {
      if (Date.now() - lastPlayAttemptAt < 1000) return;
      lastPlayAttemptAt = Date.now();
      tryPlayRef.current(video);
    };

    const seekSafely = (video: HTMLVideoElement, position: number, resume: boolean) => {
      lastSeekAt = Date.now();
      onSeekRef.current?.();
      const wasPlaying = !video.paused;
      if (wasPlaying) video.pause();
      try {
        video.currentTime = Math.max(0, position);
      } catch {
        // Métadonnées pas encore chargées : la boucle réessaiera au prochain tour.
        return;
      }
      if (resume && wasPlaying) {
        const onSeeked = () => {
          video.removeEventListener("seeked", onSeeked);
          tryPlayRef.current(video);
        };
        video.addEventListener("seeked", onSeeked, { once: true });
        setTimeout(() => {
          video.removeEventListener("seeked", onSeeked);
          if (video.paused && stateRef.current.state === "playing") tryPlayRef.current(video);
        }, 1500);
      }
    };

    const tick = () => {
      const video = videoRef.current;
      const st = stateRef.current;
      const anchor = st.clock;
      if (!video || !video.src || !anchor || !st.current_video) return;
      if (st.state !== "playing" && st.state !== "paused") return;
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) return;

      const now = serverNowRef.current();
      const target = anchorPosition(anchor, now);
      const nominal = anchor.rate;

      if (video.seeking) return;

      // --- Pause (ou horloge arrêtée) : figé à la position de l'ancre.
      if (st.state === "paused" || !anchor.running) {
        if (!video.paused) video.pause();
        if (video.playbackRate !== nominal) video.playbackRate = nominal;
        correcting = false;
        if (Math.abs(video.currentTime - target) > HOLD_SEEK_THRESHOLD_S) {
          seekSafely(video, target, false);
        }
        return;
      }

      // --- Avant l'instant de départ : en attente, à la bonne position.
      const wait = msUntilStart(anchor, now);
      if (wait > 0) {
        if (!video.paused) video.pause();
        if (Math.abs(video.currentTime - anchor.pos) > HOLD_SEEK_THRESHOLD_S) {
          seekSafely(video, anchor.pos, false);
          return;
        }
        if (wait <= START_ARM_WINDOW_MS && startTimer === null) {
          startTimer = setTimeout(() => {
            startTimer = null;
            const v = videoRef.current;
            if (v && v.paused && stateRef.current.state === "playing") tryPlayRef.current(v);
          }, wait);
        }
        return;
      }

      // --- En lecture, instant de départ passé.
      if (video.paused) {
        // Départ manqué (média pas prêt à l'heure) : on rejoint la position
        // courante d'abord si l'écart est grand, sinon on relance simplement.
        if (Math.abs(video.currentTime - target) > HOLD_SEEK_THRESHOLD_S) {
          seekSafely(video, target + SEEK_LATENCY_COMPENSATION_S, true);
        }
        playThrottled(video);
        return;
      }
      if (video.readyState < HTMLMediaElement.HAVE_FUTURE_DATA) return; // mise en mémoire tampon
      if (Date.now() - lastSeekAt < SETTLE_AFTER_SEEK_MS) return;

      const plan = planDrift(video.currentTime - target, nominal, correcting);
      if (plan.action === "seek") {
        if (Date.now() - lastSeekAt >= MIN_MS_BETWEEN_SEEKS) {
          correcting = false;
          video.playbackRate = nominal;
          seekSafely(video, target + SEEK_LATENCY_COMPENSATION_S, true);
        }
        return;
      }
      correcting = plan.action === "rate";
      if (Math.abs(video.playbackRate - plan.playbackRate) > 0.001) {
        video.playbackRate = plan.playbackRate;
      }
    };

    const id = setInterval(tick, FOLLOW_INTERVAL_MS);
    return () => {
      clearInterval(id);
      if (startTimer) clearTimeout(startTimer);
    };
  }, [videoRef]);
}
