"use client";

import { useCallback, useEffect, useRef, type MutableRefObject } from "react";
import { applyRoute, type OutputDevice, type RadioRoute, type RouteStatus, type SinkContext } from "@/lib/audioRoute";
import type { MixStage } from "@/lib/radioMixGraph";

/** Sorties audio du navigateur (libellés vides tant qu'aucune permission média n'a été accordée : voir `audioRoute.ts`). */
async function listBrowserOutputs(): Promise<OutputDevice[]> {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((d) => d.kind === "audiooutput").map((d) => ({ deviceId: d.deviceId, label: d.label }));
}

interface UseAudioRouteOptions {
  /** Contexte audio du lecteur (créé au déverrouillage). */
  ctxRef: MutableRefObject<AudioContext | null>;
  /** Étage de mixage : porte de sourdine du repli « couper ». */
  stageRef: MutableRefObject<MixStage | null>;
  /** Route publiée par le serveur pour cette sortie radio (null = sortie par défaut). */
  route: RadioRoute | null;
  /** Vrai une fois le graphe audio construit. */
  ready: boolean;
  connected: boolean;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
}

/**
 * Applique la route audio de la sortie radio au navigateur de CE lecteur (`AudioContext.setSinkId`) et rapporte le
 * résultat au serveur (`radio_report_route`) : l'interface Périphériques affiche ce qui s'est réellement passé, et le
 * serveur ne déplace un flux (Linux) que si le navigateur n'a pas pu s'en charger. Rejoué quand la route change, quand
 * le navigateur voit arriver ou partir un périphérique audio (`devicechange`) et après chaque reconnexion.
 */
export function useAudioRoute({ ctxRef, stageRef, route, ready, connected, sendCommand }: UseAudioRouteOptions): void {
  const routeRef = useRef(route);
  const sentRef = useRef("");
  const sendRef = useRef(sendCommand);
  useEffect(() => {
    routeRef.current = route;
    sendRef.current = sendCommand;
  });

  const run = useCallback(async () => {
    const ctx = ctxRef.current;
    if (!ctx || !ready) return;
    const current = routeRef.current;
    const status: RouteStatus = await applyRoute(ctx as unknown as SinkContext, current, {
      env: {
        secure: typeof window !== "undefined" && window.isSecureContext,
        canSetSinkId: typeof (ctx as unknown as SinkContext).setSinkId === "function" && !!navigator.mediaDevices?.enumerateDevices,
      },
      listOutputs: listBrowserOutputs,
      setMuted: (muted) => stageRef.current?.setRouteMuted(muted),
    });
    // Sans route, rien à rapporter (sauf pour effacer un ancien rapport).
    if (!current && !sentRef.current) return;
    if (sentRef.current === status) return;
    sentRef.current = status;
    sendRef.current("radio_report_route", { status });
  }, [ctxRef, stageRef, ready]);

  const routeKey = JSON.stringify(route);
  useEffect(() => {
    void run();
    // `routeKey` résume le contenu de `route` (l'objet est recréé à chaque évènement d'état)
  }, [run, routeKey]);

  // Après une reconnexion le serveur a perdu notre rapport.
  useEffect(() => {
    if (!connected) return;
    sentRef.current = "";
    void run();
  }, [connected, run]);

  useEffect(() => {
    const devices = typeof navigator !== "undefined" ? navigator.mediaDevices : undefined;
    if (!devices?.addEventListener) return;
    const onChange = () => void run();
    devices.addEventListener("devicechange", onChange);
    return () => devices.removeEventListener("devicechange", onChange);
  }, [run]);
}
