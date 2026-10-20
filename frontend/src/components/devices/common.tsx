"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { devicesRequest, type ApiError, type Capabilities } from "@/lib/devicesApi";

export type Notify = (message: string, type?: "success" | "error" | "warning") => void;

export interface SectionProps {
  caps: Capabilities;
  local: boolean;
  /** Incrémenté à chaque évènement `devices_changed` : déclenche une relecture. */
  refreshKey: number;
  /** Raccourci depuis la carte : élément à mettre en évidence (adresse Bluetooth, SSID, identifiant de sortie). */
  focusId?: string | null;
  /** Change à chaque raccourci (même élément, nouveau clic). */
  focusNonce?: number;
  notify: Notify;
  t: (key: string, params?: Record<string, string | number>) => string;
}

/** Message lisible pour une erreur d'API : traduction du code si elle existe, sinon le message du serveur. */
export function errorText(error: ApiError, t: SectionProps["t"]): string {
  const key = `devices.errors.${error.code}`;
  const translated = t(key);
  if (translated !== key) return translated;
  return error.message || t("devices.errors.generic");
}

/** Charge une ressource `/api/devices/<path>` ; relue sur `refreshKey` et à la demande (`reload`). */
export function useDevicesResource<T>(path: string, refreshKey: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);

  const reload = useCallback(async () => {
    const result = await devicesRequest<T>(path);
    if (!alive.current) return;
    if (result.ok) {
      setData(result.data);
      setError(null);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [path]);

  useEffect(() => {
    alive.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement d'une ressource externe (API), pas un calcul dérivable au rendu
    void reload();
    return () => {
      alive.current = false;
    };
  }, [reload, refreshKey]);

  return { data, error, loading, reload };
}

/** Ouvre un réglage du système sur la machine (Android : Wi-Fi, Bluetooth, son). */
export async function openSystemSettings(target: "wifi" | "bluetooth" | "sound", notify: Notify, t: SectionProps["t"]) {
  const result = await devicesRequest<{ ok: boolean }>("/system-settings", { body: { target } });
  if (result.ok) notify(t("devices.settingsOpened"), "success");
  else notify(errorText(result.error, t), "error");
}

/** Met en évidence (défilement + halo bref) l'élément `[data-focus-id]` visé par un raccourci de la carte. */
export function useFocusFlash(focusId: string | null | undefined, nonce: number | undefined, ready: boolean) {
  useEffect(() => {
    if (!focusId || !ready) return;
    const frame = requestAnimationFrame(() => {
      const el = Array.from(document.querySelectorAll<HTMLElement>("[data-focus-id]")).find((node) => node.dataset.focusId === focusId);
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      el.classList.add("dv-flash");
      setTimeout(() => el.classList.remove("dv-flash"), 2200);
    });
    return () => cancelAnimationFrame(frame);
  }, [focusId, nonce, ready]);
}
