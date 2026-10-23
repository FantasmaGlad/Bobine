"use client";

import { useEffect, useRef, useState } from "react";
import type { RadioOutputId } from "@/lib/devicesApi";
import { clampMix, smoothLevel, type MeterId, type RadioMix } from "@/lib/radioMix";
import { clampSound, type RadioSoundSettings } from "@/lib/radioSound";
import type { RadioRoute } from "@/lib/audioRoute";

/** Ce que l'interface Périphériques suit d'une sortie radio en direct. */
export interface RadioFeedChannel {
  playing: boolean;
  /** Titre de la piste en cours (null à l'arrêt). */
  title: string | null;
  mix: RadioMix;
  sound: RadioSoundSettings;
  route: RadioRoute | null;
}

export type FeedLevels = Partial<Record<MeterId, number>>;

export interface RadioFeed {
  connected: boolean;
  channels: Partial<Record<RadioOutputId, RadioFeedChannel>>;
  levels: Partial<Record<RadioOutputId, FeedLevels>>;
}

const OUTPUTS: RadioOutputId[] = ["radio_cable", "radio_network"];
/** Le serveur garde le vumètre actif 12 s après la dernière demande : on la renouvelle bien avant. */
const METER_RENEW_MS = 5000;
/** Sans nouvelle mesure depuis ce délai (lecteur en pause, fermé), les aiguilles retombent. */
const LEVEL_STALE_MS = 600;
const DECAY_TICK_MS = 150;

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const host = window.location.port === "3000" ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}

/**
 * Suit en direct les deux sorties radio (état de lecture, mixage, route) pour le graphe et la table de mixage, sans
 * jamais se déclarer lecteur (aucun `identify` : pas de rôle primaire, aucun effet sur la diffusion). Quand `metering`
 * est vrai, demande au lecteur primaire de chaque sortie de mesurer ses niveaux (`radio_meter`, bail renouvelé).
 * Reconnexion automatique avec attente croissante.
 */
export function useRadioFeed(enabled: boolean, metering: boolean): RadioFeed {
  const [connected, setConnected] = useState(false);
  const [channels, setChannels] = useState<RadioFeed["channels"]>({});
  const [levels, setLevels] = useState<RadioFeed["levels"]>({});
  const stampsRef = useRef<Partial<Record<RadioOutputId, number>>>({});
  const meteringRef = useRef(metering);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    meteringRef.current = metering;
    const ws = socketRef.current;
    if (metering && ws && ws.readyState === WebSocket.OPEN) {
      for (const channel of OUTPUTS) ws.send(JSON.stringify({ command: "radio_meter", params: { channel } }));
    }
  }, [metering]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let renew: ReturnType<typeof setInterval> | undefined;
    let delay = 1000;

    const requestMeters = (ws: WebSocket) => {
      if (!meteringRef.current || ws.readyState !== WebSocket.OPEN) return;
      for (const channel of OUTPUTS) ws.send(JSON.stringify({ command: "radio_meter", params: { channel } }));
    };

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getWsUrl());
      socketRef.current = ws;
      ws.onopen = () => {
        delay = 1000;
        setConnected(true);
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: OUTPUTS } }));
        requestMeters(ws);
        renew = setInterval(() => requestMeters(ws), METER_RENEW_MS);
      };
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.event === "ping") {
            ws.send(JSON.stringify({ command: "pong" }));
          } else if (message.event === "state_change" && OUTPUTS.includes(message.channel)) {
            const data = message.data ?? {};
            setChannels((current) => ({
              ...current,
              [message.channel]: {
                playing: !!data.playing,
                title: data.current_track?.title ?? null,
                mix: clampMix(data.mix),
                sound: clampSound(data.sound),
                route: data.route ?? null,
              },
            }));
          } else if (message.event === "radio_levels" && OUTPUTS.includes(message.channel)) {
            stampsRef.current[message.channel as RadioOutputId] = Date.now();
            setLevels((current) => ({ ...current, [message.channel]: { ...current[message.channel as RadioOutputId], ...message.levels } }));
          }
        } catch {
          /* message illisible : ignoré */
        }
      };
      ws.onclose = () => {
        if (renew) clearInterval(renew);
        setConnected(false);
        if (socketRef.current === ws) socketRef.current = null;
        if (cancelled) return;
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      if (renew) clearInterval(renew);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [enabled]);

  // Retombée des aiguilles quand plus aucune mesure n'arrive.
  useEffect(() => {
    if (!enabled || !metering) return;
    const id = setInterval(() => {
      const now = Date.now();
      setLevels((current) => {
        let changed = false;
        const next: RadioFeed["levels"] = {};
        for (const channel of OUTPUTS) {
          const meters = current[channel];
          if (!meters) continue;
          const stale = now - (stampsRef.current[channel] ?? 0) > LEVEL_STALE_MS;
          const entry: FeedLevels = {};
          for (const [id, value] of Object.entries(meters) as Array<[MeterId, number]>) {
            const lowered = stale ? smoothLevel(value, 0) : value;
            if (lowered !== value) changed = true;
            entry[id] = lowered;
          }
          next[channel] = entry;
        }
        return changed ? next : current;
      });
    }, DECAY_TICK_MS);
    return () => clearInterval(id);
  }, [enabled, metering]);

  return { connected, channels, levels };
}
