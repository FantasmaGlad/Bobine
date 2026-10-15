"use client";

import { useEffect, useRef } from "react";
import { anchorPosition, msUntilStart, planDrift, type ClockAnchor } from "@/lib/playbackClock";

// Cadence de la boucle de suivi : assez courte pour tenir une précision de
// l'ordre de 100 ms, assez longue pour ne rien coûter (comparaison de deux
// nombres, aucun re-rendu React).
const FOLLOW_INTERVAL_MS = 200;
// Au-delà de cet écart (s) à l'arrêt/avant le départ, on replace le média.
const HOLD_SEEK_THRESHOLD_S = 0.25;
// Départ en retard : au-delà de cet écart (s) on saute à la position cible, en
// dessous on démarre tel quel et la correction de vitesse comble l'écart.
const LATE_START_SEEK_THRESHOLD_S = 1.0;
// Après un `seek`, on laisse le décodeur se stabiliser avant de juger la dérive,
// et on n'en refait pas un autre tout de suite (anti-boucle).
const SETTLE_AFTER_SEEK_MS = 1500;
const MIN_MS_BETWEEN_SEEKS = 4000;
// Latence moyenne d'un seek (s) compensée en visant légèrement devant.
const SEEK_LATENCY_COMPENSATION_S = 0.2;
// Fenêtre dans laquelle on arme le minuteur précis de démarrage synchronisé.
const START_ARM_WINDOW_MS = 600;

/** Ce que le suiveur doit appliquer à l'élément média, déduit de l'état courant. */
export interface ClockTarget {
  anchor: ClockAnchor | null | undefined;
  /** Lecture ou pause demandée ; null = rien à suivre (aucun média concerné). */
  mode: "playing" | "paused" | null;
  /** Identifie le média courant (id de cours / de piste) pour réagir à un changement. */
  key?: string | number | null;
}

interface Options<S> {
  mediaRef: { current: HTMLMediaElement | null };
  state: S;
  /** Extrait de l'état la cible à suivre (vidéo, piste audio du mode coach, radio...). */
  select: (state: S) => ClockTarget;
  /** Désactive le suivi sans démonter le hook (ex. poste primaire de la radio, qui reste la source). */
  enabled?: boolean;
  /** Vérifie que l'élément joue bien le média visé (`key`) avant d'agir : évite de
   * « corriger » un lecteur qui charge encore le cours précédent (double lecteur A/B). */
  isMediaForKey?: (el: HTMLMediaElement, key: string | number | null | undefined) => boolean;
  /** Heure serveur estimée (epoch, ms). */
  serverNow: () => number;
  /** Lance la lecture avec le repli d'autoplay propre à la page. */
  tryPlay: (el: HTMLMediaElement | null | undefined) => void;
  /** Notifie qu'un `seek` vient d'être émis (chiens de garde de la page). */
  onSeek?: () => void;
}

/**
 * Fait suivre à un élément média (<video> ou <audio>) l'horloge de lecture
 * publiée par le serveur :
 *  - avant l'instant de départ : maintenu en pause à la bonne position
 *    (préchargé), puis `play()` lancé à l'instant exact -> tous les écrans
 *    démarrent ensemble ;
 *  - en lecture : dérive mesurée en continu et corrigée par un ajustement de
 *    `playbackRate` (±5 %), SANS `seek` ; un seul `seek` au-delà de 2 s ;
 *  - en pause : maintenu en pause à la position de l'ancre ;
 *  - ordre explicite (changement d'epoch) : appliqué immédiatement.
 * Ne touche jamais à un média en cours de chargement ou de seek.
 */
export function useMediaClockFollower<S>({ mediaRef, state, select, enabled = true, isMediaForKey, serverNow, tryPlay, onSeek }: Options<S>) {
  const stateRef = useRef(state);
  const selectRef = useRef(select);
  const enabledRef = useRef(enabled);
  const isMediaForKeyRef = useRef(isMediaForKey);
  const serverNowRef = useRef(serverNow);
  const tryPlayRef = useRef(tryPlay);
  const onSeekRef = useRef(onSeek);
  useEffect(() => {
    stateRef.current = state;
    selectRef.current = select;
    enabledRef.current = enabled;
    isMediaForKeyRef.current = isMediaForKey;
    serverNowRef.current = serverNow;
    tryPlayRef.current = tryPlay;
    onSeekRef.current = onSeek;
  });

  // Fonction de suivi exposée à l'effet de réaction ci-dessous (le corps
  // vit dans l'effet principal, qui en possède l'état interne).
  const tickRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let correcting = false;
    let lastSeekAt = 0;
    // Dernière epoch d'ancre traitée : un changement = un ORDRE explicite
    // (télécommande, /grid, planning), à appliquer immédiatement.
    let handledEpoch: number | undefined;
    let lastPlayAttemptAt = 0;
    let startTimer: ReturnType<typeof setTimeout> | null = null;

    // Relance de lecture limitée à 1/s : un autoplay refusé par le navigateur
    // ne doit pas être retenté (et son repli muet re-déclenché) toutes les 200 ms.
    const playThrottled = (video: HTMLMediaElement) => {
      if (Date.now() - lastPlayAttemptAt < 1000) return;
      lastPlayAttemptAt = Date.now();
      tryPlayRef.current(video);
    };

    const seekSafely = (video: HTMLMediaElement, position: number, resume: boolean) => {
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
          if (video.paused && selectRef.current(stateRef.current).mode === "playing") tryPlayRef.current(video);
        }, 1500);
      }
    };

    const tick = () => {
      if (!enabledRef.current) return;
      const video = mediaRef.current;
      const target0 = selectRef.current(stateRef.current);
      const anchor = target0.anchor;
      if (!video || !video.src || !anchor || target0.mode === null) return;
      // Média terminé : ne jamais le relancer (l'horloge, elle, continue d'avancer).
      if (video.ended) return;
      if (isMediaForKeyRef.current && !isMediaForKeyRef.current(video, target0.key)) return;
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) return;

      const now = serverNowRef.current();
      const target = anchorPosition(anchor, now);
      const nominal = anchor.rate;

      if (video.seeking) return;

      // --- Pause (ou horloge arrêtée) : figé à la position de l'ancre.
      if (target0.mode === "paused" || !anchor.running) {
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
            const v = mediaRef.current;
            if (v && v.paused && selectRef.current(stateRef.current).mode === "playing") tryPlayRef.current(v);
          }, wait);
        }
        return;
      }

      // --- En lecture, instant de départ passé.
      if (video.paused) {
        // Départ manqué (média pas prêt à l'heure : l'horloge serveur avance
        // pendant l'ouverture du flux) : un petit retard est rattrapé par la
        // vitesse après le démarrage — AUCUN seek (reset du décodeur) pour
        // quelques centaines de ms ; au-delà de 1 s on rejoint la position.
        if (Math.abs(video.currentTime - target) > LATE_START_SEEK_THRESHOLD_S) {
          seekSafely(video, target + SEEK_LATENCY_COMPENSATION_S, true);
        }
        playThrottled(video);
        return;
      }
      if (video.readyState < HTMLMediaElement.HAVE_FUTURE_DATA) return; // mise en mémoire tampon
      // Ordre explicite : ni délai de grâce ni anti-boucle (deux seeks +10 s
      // consécutifs à la télécommande doivent chacun s'exécuter aussitôt).
      const explicit = anchor.epoch !== undefined && anchor.epoch !== handledEpoch;
      if (anchor.epoch !== undefined) handledEpoch = anchor.epoch;
      if (!explicit && Date.now() - lastSeekAt < SETTLE_AFTER_SEEK_MS) return;

      const plan = planDrift(video.currentTime - target, nominal, correcting, explicit);
      if (plan.action === "seek") {
        if (explicit || Date.now() - lastSeekAt >= MIN_MS_BETWEEN_SEEKS) {
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

    tickRef.current = tick;
    const id = setInterval(tick, FOLLOW_INTERVAL_MS);
    // Onglet masqué : Firefox (comme Chromium) ramène les minuteurs à ≥ 1 s, la
    // dérive peut donc s'accumuler. Au retour au premier plan, on recale TOUT
    // DE SUITE au lieu d'attendre le tour suivant.
    const onVisible = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      tickRef.current = null;
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
      if (startTimer) clearTimeout(startTimer);
    };
  }, [mediaRef]);

  // Réaction IMMÉDIATE à un ordre (play, pause, seek, nouveau cours) : sans
  // cela, une commande attendait jusqu'à FOLLOW_INTERVAL_MS (200 ms) le prochain
  // tour de la boucle avant d'être appliquée à l'écran.
  const current = select(state);
  const anchor = current.anchor;
  useEffect(() => {
    tickRef.current?.();
  }, [anchor?.at_ms, anchor?.running, anchor?.pos, anchor?.rate, anchor?.epoch, current.mode, current.key, enabled]);
}
