"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { translate, translateList, type Language } from "@/lib/i18n";

// "les-mills-sombre" est la clé interne historique du thème "Sombre" (réf.
// mission thèmes cinéma) — conservée telle quelle pour ne rien casser sur
// les installations existantes, seul le libellé affiché change.
export type Theme = "les-mills-sombre" | "clair" | "lune" | "menthe" | "automne" | "hiver" | "chili" | "ciel" | "orchidee" | "taupe" | "charbon" | "beige" | "lavande";

export const THEME_VALUES: Theme[] = ["les-mills-sombre", "clair", "lune", "menthe", "automne", "hiver", "chili", "ciel", "orchidee", "taupe", "charbon", "beige", "lavande"];

interface AppSettingsContextValue {
  theme: Theme;
  language: Language;
  t: (key: string, params?: Record<string, string | number>) => string;
  tList: (key: string) => string[];
  setTheme: (theme: Theme) => void;
  setLanguage: (language: Language) => void;
  hasCustomLogo: boolean;
  /** Incrémenté à chaque évènement logo (upload/suppression) : à ajouter en
   * cache-buster (`?v=`) sur l'URL du logo custom, car l'URL elle-même
   * (/api/branding/logo.png) ne change pas quand un logo remplace un autre
   * — sans ce compteur, le navigateur pourrait servir l'ancien fichier
   * depuis son cache. */
  logoVersion: number;
  launchAnimationEnabled: boolean;
  setLaunchAnimationEnabled: (value: boolean) => void;
  refreshBranding: () => void;
}

const DEFAULT_THEME: Theme = "les-mills-sombre";
const DEFAULT_LANGUAGE: Language = "fr";

const AppSettingsContext = createContext<AppSettingsContextValue>({
  theme: DEFAULT_THEME,
  language: DEFAULT_LANGUAGE,
  t: (key) => key,
  tList: () => [],
  setTheme: () => {},
  setLanguage: () => {},
  hasCustomLogo: false,
  logoVersion: 0,
  launchAnimationEnabled: true,
  setLaunchAnimationEnabled: () => {},
  refreshBranding: () => {},
});

export function useAppSettings() {
  return useContext(AppSettingsContext);
}

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

/**
 * Thème (réf. UX1.1-UX1.4) et langue (réf. UX1.5) partagés par toute
 * l'application — PC, mobile ET écran cinéma (ce provider enveloppe
 * ClientLayout dans son ensemble, y compris les routes /kiosk et /coach qui
 * court-circuitent la coquille de navigation, réf. UX2.3/tâche 11.4).
 *
 * Persistance côté serveur (table `settings`, réf. Lot 9) : chargée une fois
 * au montage. Le flash du mauvais thème au tout premier rendu est évité par
 * un petit script bloquant dans layout.tsx qui applique la valeur mise en
 * cache localStorage avant l'hydratation React — ce provider ne fait que
 * garder React et le DOM synchronisés ensuite et persister les changements.
 */
export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [language, setLanguageState] = useState<Language>(DEFAULT_LANGUAGE);
  const [hasCustomLogo, setHasCustomLogo] = useState(false);
  const [logoVersion, setLogoVersion] = useState(0);
  const [launchAnimationEnabled, setLaunchAnimationEnabledState] = useState(true);

  const refreshBranding = useCallback(() => {
    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        if (typeof data.has_custom_logo === "boolean") {
          setHasCustomLogo(data.has_custom_logo);
          setLogoVersion((v) => v + 1);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    try {
      const cachedTheme = localStorage.getItem("olc-theme") as Theme | null;
      const cachedLanguage = localStorage.getItem("olc-language") as Language | null;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise l'état avec le cache localStorage au montage, même motif que le chargement initial ailleurs dans le projet (library/playlists/schedule)
      if (cachedTheme) setThemeState(cachedTheme);
      if (cachedLanguage) setLanguageState(cachedLanguage);
    } catch {
      // localStorage indisponible (navigation privée stricte) : le défaut suffit.
    }

    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        if (THEME_VALUES.includes(data.theme)) {
          setThemeState(data.theme);
        }
        if (data.language === "fr" || data.language === "en") {
          setLanguageState(data.language);
        }
        if (typeof data.intro_animation_enabled === "boolean") {
          setLaunchAnimationEnabledState(data.intro_animation_enabled);
        }
        if (typeof data.has_custom_logo === "boolean") {
          setHasCustomLogo(data.has_custom_logo);
          setLogoVersion((v) => v + 1);
        }
      })
      .catch(() => {});
  }, []);

  // Synchronisation temps réel (correctif "le thème ne se synchronise pas
  // avec l'écran cinéma") : jusqu'ici le thème n'était chargé qu'une fois au
  // montage (fetch ci-dessus) — un changement décidé depuis l'admin pendant
  // que /cinema (ou tout autre écran) était déjà ouvert n'y apparaissait
  // jamais sans rechargement manuel de la page. Connexion WebSocket dédiée
  // et minimale (le backend diffuse l'évènement sur le même canal que la
  // lecture, réutilisé ici passivement — aucune commande n'est jamais
  // envoyée) plutôt que de dépendre de usePlaybackSocket, qui n'est pas
  // toujours monté au-dessus de ce contexte.
  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (cancelled || typeof window === "undefined") return;
      const isDevServer = window.location.port === "3000";
      const host = isDevServer ? "localhost:8001" : window.location.host;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(`${protocol}//${host}/ws/playback`);
      ws.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data);
          if (parsed.event === "ping") {
            ws?.send(JSON.stringify({ command: "pong" }));
            return;
          }
          if (parsed.event === "settings_change") {
            if (THEME_VALUES.includes(parsed.theme)) {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- réaction à un évènement externe temps réel, pas un calcul dérivable au rendu
              setThemeState(parsed.theme);
            }
            if (parsed.language === "fr" || parsed.language === "en") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setLanguageState(parsed.language);
            }
            if (typeof parsed.intro_animation_enabled === "boolean") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setLaunchAnimationEnabledState(parsed.intro_animation_enabled);
            }
            if (typeof parsed.has_custom_logo === "boolean") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setHasCustomLogo(parsed.has_custom_logo);
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setLogoVersion((v) => v + 1);
            }
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
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("olc-theme", theme);
    } catch {
      // ignore
    }
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = language;
    try {
      localStorage.setItem("olc-language", language);
    } catch {
      // ignore
    }
  }, [language]);

  const persist = useCallback((payload: Record<string, string | boolean>) => {
    fetch(getApiUrl("/settings"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});
  }, []);

  const setTheme = useCallback(
    (value: Theme) => {
      setThemeState(value);
      persist({ theme: value });
    },
    [persist]
  );

  const setLanguage = useCallback(
    (value: Language) => {
      setLanguageState(value);
      persist({ language: value });
    },
    [persist]
  );

  const setLaunchAnimationEnabled = useCallback(
    (value: boolean) => {
      setLaunchAnimationEnabledState(value);
      persist({ intro_animation_enabled: value });
    },
    [persist]
  );

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => translate(language, key, params),
    [language]
  );

  const tList = useCallback((key: string) => translateList(language, key), [language]);

  // useMemo (réf. revue de code) : avant l'ajout du branding/toggle, AppLogo
  // était un <img> statique sans hook, jamais concerné. Il consomme
  // désormais ce contexte sur 8 écrans (dont le kiosque, actif en continu) —
  // sans mémoïsation, CHAQUE render de ce Provider (y compris pour un état
  // qu'aucun consommateur ne lit, si un futur champ est ajouté ici) recrée
  // un objet `value` de référence différente et force tous les
  // useAppSettings() à re-render, AppLogo inclus.
  const value = React.useMemo(
    () => ({
      theme,
      language,
      t,
      tList,
      setTheme,
      setLanguage,
      hasCustomLogo,
      logoVersion,
      launchAnimationEnabled,
      setLaunchAnimationEnabled,
      refreshBranding,
    }),
    [theme, language, t, tList, setTheme, setLanguage, hasCustomLogo, logoVersion, launchAnimationEnabled, setLaunchAnimationEnabled, refreshBranding]
  );

  return (
    <AppSettingsContext.Provider value={value}>
      {children}
    </AppSettingsContext.Provider>
  );
}
