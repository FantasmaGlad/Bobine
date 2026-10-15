"use client";

import { useEffect, useRef } from "react";
import {
  buildOutputUrl,
  isLoopbackHost,
  resolveChannel,
  shouldFollowInitialOutput,
  type DisplayChannel,
  type DisplayPage,
} from "@/lib/displayChannel";

/**
 * Vrai si le navigateur tourne sur la machine qui héberge le serveur (kiosk
 * Chromium du Wyse via 127.0.0.1, cf. install.sh KIOSK_URL, `Presentation`
 * HDMI Android). Sert à repérer l'ÉCRAN PHYSIQUE local ; ce n'est plus la
 * règle d'appartenance à un canal — voir `getDisplayChannel()`.
 */
export function isWiredDisplay(): boolean {
  if (typeof window === "undefined") return false;
  return isLoopbackHost(window.location.hostname);
}

/**
 * Canal de diffusion de CETTE page : `?channel=` explicite d'abord, sinon le
 * défaut historique de la page (cf. displayChannel.ts). Règle UNIQUE partagée
 * par /kiosk et /cinema.
 */
export function getDisplayChannel(page: DisplayPage): DisplayChannel {
  if (typeof window === "undefined") return "cable";
  return resolveChannel(window.location.search, window.location.hostname, page).channel;
}

/**
 * Fait suivre à la page affichée la sortie choisie par l'admin pour SON
 * canal.
 *
 * Correctif « kiosk et cinéma dépendants » : seul le canal CÂBLÉ applique la
 * valeur stockée dès le montage — il doit démarrer dans le bon mode au boot.
 * Un écran du RÉSEAU n'est redirigé que lorsqu'un admin bascule réellement le
 * canal PENDANT que la page est ouverte : quelqu'un qui ouvre volontairement
 * /cinema sur son téléphone y reste, même si le canal réseau est réglé sur
 * « kiosk ».
 *
 * Correctif « 127.0.0.1 / canal Réseau » : la cible suivie est celle du canal
 * RÉSOLU de la page (et non du seul nom d'hôte), et la redirection conserve la
 * query string — donc `?channel=network`. Avant, un écran réseau ouvert en
 * 127.0.0.1 suivait la sortie du canal câblé puis perdait son paramètre.
 */
export function useDisplayOutputRedirect(
  current: "kiosk" | "cinema",
  cableOutput: "kiosk" | "cinema" | null,
  networkOutput: "kiosk" | "cinema" | null,
) {
  // Dernière valeur observée pour le canal de cet appareil : permet de
  // distinguer la valeur initiale (chargée du serveur au montage) d'un vrai
  // changement poussé par l'admin (suivi partout).
  const lastSeenRef = useRef<"kiosk" | "cinema" | null>(null);

  useEffect(() => {
    const { channel } = resolveChannel(window.location.search, window.location.hostname, current);
    const target = channel === "cable" ? cableOutput : networkOutput;
    if (!target) return;

    const previous = lastSeenRef.current;
    lastSeenRef.current = target;

    if (target === current) return;
    if (!shouldFollowInitialOutput(channel) && previous === null) return;
    window.location.replace(buildOutputUrl(target, window.location.search, channel));
  }, [cableOutput, networkOutput, current]);
}
