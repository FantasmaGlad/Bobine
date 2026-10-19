"use client";

import { useEffect, useRef } from "react";
import {
  decideOutputRedirect,
  isLoopbackHost,
  resolveChannel,
  shouldEvaluateRedirect,
  type DisplayChannel,
  type DisplayOutput,
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
  // Rendu serveur (export statique) : la radio est « réseau » par défaut, comme /radio nu.
  if (typeof window === "undefined") return page === "radio" ? "network" : "cable";
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
 * Sortie « radio » (câblé uniquement) : /kiosk et /cinema du canal câblé naviguent vers
 * /radio?channel=cable quand l'admin bascule l'écran câblé sur Radio, et la page radio
 * câblée repart vers kiosk/cinéma sur une bascule faite EN DIRECT (jamais au montage).
 * Un poste radio réseau ne suit jamais rien. Décision dans `decideOutputRedirect`.
 *
 * Correctif « 127.0.0.1 / canal Réseau » : la cible suivie est celle du canal
 * RÉSOLU de la page (et non du seul nom d'hôte), et la redirection conserve la
 * query string — donc `?channel=network`. Avant, un écran réseau ouvert en
 * 127.0.0.1 suivait la sortie du canal câblé puis perdait son paramètre.
 */
export function useDisplayOutputRedirect(
  current: DisplayPage,
  cableOutput: DisplayOutput | null,
  networkOutput: DisplayOutput | null,
) {
  // Dernière valeur observée pour le canal de cet appareil : permet de
  // distinguer la valeur initiale (chargée du serveur au montage) d'un vrai
  // changement poussé par l'admin (suivi partout).
  const lastSeenRef = useRef<DisplayOutput | null>(null);

  useEffect(() => {
    // Seule la sortie de CE canal compte : un changement de l'autre canal ne doit jamais faire naviguer la page.
    const { channel } = resolveChannel(window.location.search, window.location.hostname, current);
    if (!shouldEvaluateRedirect(channel, cableOutput, networkOutput, lastSeenRef.current)) return;
    const decision = decideOutputRedirect(
      current,
      window.location.search,
      window.location.hostname,
      cableOutput,
      networkOutput,
      lastSeenRef.current,
    );
    lastSeenRef.current = decision.seen;
    if (decision.to) window.location.replace(decision.to);
  }, [cableOutput, networkOutput, current]);
}
