"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { translate, translateList, type Language } from "@/lib/i18n";

// "les-mills-sombre" est la clé interne historique du thème "Sombre" — conservée telle quelle pour ne rien casser sur
// les installations existantes, seul le libellé affiché change.
export type Theme =
  | "les-mills-sombre"
  | "clair"
  | "lune"
  | "menthe"
  | "automne"
  | "hiver"
  | "chili"
  | "ciel"
  | "orchidee"
  | "taupe"
  | "charbon"
  | "charbon-sombre"
  | "beige"
  | "lavande"
  | "miel"
  | "coco";

export const THEME_VALUES: Theme[] = [
  "les-mills-sombre",
  "clair",
  "lune",
  "menthe",
  "automne",
  "hiver",
  "chili",
  "ciel",
  "orchidee",
  "taupe",
  "charbon",
  "charbon-sombre",
  "beige",
  "lavande",
  "miel",
  "coco",
];

export interface NetworkInfo {
  localIp: string | null;
  port: number;
  mdnsUrl: string;
}

export type ActiveLogo = "default" | "custom";
export type UpdateChannel = "stable" | "beta" | "canary";
export type WiredDisplayMode = "dual_screen" | "headless";
/** Réglage administrateur : "auto" = dérivé des écrans externes réellement
 * connectés ; sinon forçage manuel. */
export type DisplayModeSetting = "auto" | WiredDisplayMode;

interface AppSettingsContextValue {
  theme: Theme;
  language: Language;
  t: (key: string, params?: Record<string, string | number>) => string;
  tList: (key: string) => string[];
  setTheme: (theme: Theme) => void;
  setLanguage: (language: Language) => void;
  hasCustomLogo: boolean;
  activeLogo: ActiveLogo;
  setActiveLogo: (activeLogo: ActiveLogo) => void;
  /** Incrémenté à chaque évènement logo (upload/suppression) : à ajouter en
   * cache-buster (`?v=`) sur l'URL du logo custom, car l'URL elle-même
   * (/api/branding/logo.png) ne change pas quand un logo remplace un autre
   * — sans ce compteur, le navigateur pourrait servir l'ancien fichier
   * depuis son cache. */
  logoVersion: number;
  refreshBranding: () => void;
  /** Canal de mise à jour courant (stable/beta/canary) — pilote entre autres
   * l'illustration affichée par AppLogo (une par canal, cf.
   * Assets/Images/Versions/). */
  updateChannel: UpdateChannel;
  wiredDisplayMode: WiredDisplayMode;
  setWiredDisplayMode: (mode: WiredDisplayMode) => void;
  displayModeSetting: DisplayModeSetting;
  setDisplayModeSetting: (setting: DisplayModeSetting) => void;
  /** Nombre d'écrans externes détectés par la plateforme (null = aucun rapport). */
  displayExternalCount: number | null;
  waitTimeBetweenCourses: number;
  /** IP LAN, port et URL mDNS de CET appareil — source déjà fiable pour la
   * découverte réseau (`_get_local_ip()` côté backend), réutilisée pour
   * l'en-tête mobile (IP/URL affichée à la place du logo) sans dupliquer
   * d'appel réseau dédié : ce contexte interroge déjà `/api/settings`. */
  network: NetworkInfo;
}

// "clair" : version claire du thème
// Les Mills par défaut (même accent rouge #e4002b que "les-mills-sombre",
// cf. THEME_SWATCHES dans app/settings/page.tsx) — premier écran vu à
// l'installation avant tout réglage utilisateur.
const DEFAULT_THEME: Theme = "clair";
const DEFAULT_LANGUAGE: Language = "fr";
const DEFAULT_WIRED_DISPLAY_MODE: WiredDisplayMode = "headless";
const DEFAULT_NETWORK: NetworkInfo = { localIp: null, port: 8000, mdnsUrl: "http://bobine.local" };

const AppSettingsContext = createContext<AppSettingsContextValue>({
  theme: DEFAULT_THEME,
  language: DEFAULT_LANGUAGE,
  t: (key) => key,
  tList: () => [],
  setTheme: () => {},
  setLanguage: () => {},
  hasCustomLogo: false,
  activeLogo: "default",
  setActiveLogo: () => {},
  logoVersion: 0,
  refreshBranding: () => {},
  updateChannel: "stable",
  wiredDisplayMode: DEFAULT_WIRED_DISPLAY_MODE,
  setWiredDisplayMode: () => {},
  displayModeSetting: "auto",
  setDisplayModeSetting: () => {},
  displayExternalCount: null,
  waitTimeBetweenCourses: 0,
  network: DEFAULT_NETWORK,
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
 * Thème et langue partagés par toute
 * l'application — PC, mobile ET écran cinéma (ce provider enveloppe
 * ClientLayout dans son ensemble, y compris les routes /kiosk et /coach qui
 * court-circuitent la coquille de navigation).
 *
 * Persistance côté serveur (table `settings`) : chargée une fois
 * au montage. Le flash du mauvais thème au tout premier rendu est évité par
 * un petit script bloquant dans layout.tsx qui applique la valeur mise en
 * cache localStorage avant l'hydratation React — ce provider ne fait que
 * garder React et le DOM synchronisés ensuite et persister les changements.
 */
export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [language, setLanguageState] = useState<Language>(DEFAULT_LANGUAGE);
  const [hasCustomLogo, setHasCustomLogo] = useState(false);
  const [activeLogo, setActiveLogoState] = useState<ActiveLogo>("default");
  const [logoVersion, setLogoVersion] = useState(0);
  const [wiredDisplayMode, setWiredDisplayModeState] = useState<WiredDisplayMode>(DEFAULT_WIRED_DISPLAY_MODE);
  const [waitTimeBetweenCourses, setWaitTimeBetweenCourses] = useState<number>(0);
  const [displayModeSetting, setDisplayModeSettingState] = useState<DisplayModeSetting>("auto");
  const [displayExternalCount, setDisplayExternalCount] = useState<number | null>(null);
  const [network, setNetwork] = useState<NetworkInfo>(DEFAULT_NETWORK);
  const [updateChannel, setUpdateChannel] = useState<UpdateChannel>("stable");

  const refreshBranding = useCallback(() => {
    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        if (typeof data.has_custom_logo === "boolean") {
          setHasCustomLogo(data.has_custom_logo);
          setLogoVersion((v) => v + 1);
        }
        if (data.active_logo === "default" || data.active_logo === "custom") {
          setActiveLogoState(data.active_logo);
        }
      })
      .catch(() => {});
  }, []);

  // Facteur commun au chargement initial ET au filet de sécurité périodique
  // ci-dessous : appliquer deux fois la même logique de lecture de
  // `/api/settings` a fait diverger le code par le passé si on ne le
  // factorisait pas.
  const applySettingsPayload = useCallback((data: Record<string, unknown> | null) => {
    if (!data) return;
    if (THEME_VALUES.includes(data.theme as Theme)) {
      setThemeState(data.theme as Theme);
    }
    if (data.language === "fr" || data.language === "en") {
      setLanguageState(data.language);
    }
    if (typeof data.has_custom_logo === "boolean") {
      setHasCustomLogo(data.has_custom_logo);
      setLogoVersion((v) => v + 1);
    }
    if (data.active_logo === "default" || data.active_logo === "custom") {
      setActiveLogoState(data.active_logo);
    }
    if (data.wired_display_mode === "dual_screen" || data.wired_display_mode === "headless") {
      setWiredDisplayModeState(data.wired_display_mode);
    }
    if (data.update_channel === "stable" || data.update_channel === "beta" || data.update_channel === "canary") {
      setUpdateChannel(data.update_channel);
    }
    if (data.display_mode_setting === "auto" || data.display_mode_setting === "dual_screen" || data.display_mode_setting === "headless") {
      setDisplayModeSettingState(data.display_mode_setting);
    }
    setDisplayExternalCount(typeof data.display_external_count === "number" ? data.display_external_count : null);
    if (typeof data.wait_time_between_courses === "number") {
      setWaitTimeBetweenCourses(data.wait_time_between_courses);
    }
    if (data.network && typeof data.network === "object") {
      const net = data.network as { local_ip?: string | null; port?: number; mdns_url?: string };
      setNetwork({
        localIp: typeof net.local_ip === "string" ? net.local_ip : null,
        port: typeof net.port === "number" ? net.port : DEFAULT_NETWORK.port,
        mdnsUrl: typeof net.mdns_url === "string" ? net.mdns_url : DEFAULT_NETWORK.mdnsUrl,
      });
    }
  }, []);

  useEffect(() => {
    try {
      const cachedTheme = localStorage.getItem("olc-theme") as Theme | null;
      const cachedLanguage = localStorage.getItem("olc-language") as Language | null;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise l'état avec le cache localStorage au montage, même motif que le chargement initial ailleurs dans le projet (library/playlists/schedule)
      if (cachedTheme) setThemeState(cachedTheme);
      if (cachedLanguage) setLanguageState(cachedLanguage);
    } catch {
      // localStorage indisponible (navigation privée stricte, ou WebView
      // Android sans DOM Storage activé : confirmé en pratique que `window.localStorage`
      // vaut `null` dans la WebView tactile de l'app Android, en pratique) : le défaut/le fetch suffisent.
    }

    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then(applySettingsPayload)
      .catch(() => {});
  }, [applySettingsPayload]);

  // Filet de sécurité de resynchronisation périodique (même motif que
  // RESYNC_INTERVAL_MS dans usePlaybackSocket.ts) :
  // le chargement initial ci-dessus ne s'exécute qu'une fois, et la
  // synchronisation "temps réel" plus bas dépend d'un `settings_change`
  // reçu EN DIRECT sur une connexion WebSocket qui peut être en train de se
  // reconnecter pile au moment où l'admin change le thème (constaté en
  // pratique sur la tablette Android : un changement de thème décidé
  // pendant que /grid tournait déjà n'était jamais rattrapé sans recharger
  // la page). Ce re-fetch REST périodique referme cette fenêtre, exactement
  // comme le filet de sécurité déjà en place pour l'état de lecture.
  useEffect(() => {
    const id = setInterval(() => {
      fetch(getApiUrl("/settings"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then(applySettingsPayload)
        .catch(() => {});
    }, 15000);
    return () => clearInterval(id);
  }, [applySettingsPayload]);

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
      // N'écoute que les évènements globaux : aucun canal.
      ws.onopen = () => ws?.send(JSON.stringify({ command: "subscribe", params: { channels: [] } }));
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
            if (typeof parsed.has_custom_logo === "boolean") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setHasCustomLogo(parsed.has_custom_logo);
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setLogoVersion((v) => v + 1);
            }
            if (parsed.active_logo === "default" || parsed.active_logo === "custom") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setActiveLogoState(parsed.active_logo);
            }
            if (parsed.wired_display_mode === "dual_screen" || parsed.wired_display_mode === "headless") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setWiredDisplayModeState(parsed.wired_display_mode);
            }
            if (parsed.update_channel === "stable" || parsed.update_channel === "beta" || parsed.update_channel === "canary") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setUpdateChannel(parsed.update_channel);
            }
          }
          if (parsed.event === "display_mode_change") {
            const mode = parsed.mode || parsed.wired_display_mode;
            if (mode === "dual_screen" || mode === "headless") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setWiredDisplayModeState(mode);
            }
            // Branchement/débranchement d'un projecteur : recale aussi le
            // nombre d'écrans détectés (affiché dans les Réglages).
            fetch(getApiUrl("/settings"), { cache: "no-store" })
              .then((res) => (res.ok ? res.json() : null))
              .then(applySettingsPayload)
              .catch(() => {});
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
  }, [applySettingsPayload]);

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

  const setActiveLogo = useCallback(
    (value: ActiveLogo) => {
      setActiveLogoState(value);
      persist({ active_logo: value });
    },
    [persist]
  );

  const setWiredDisplayMode = useCallback(
    (value: WiredDisplayMode) => {
      setWiredDisplayModeState(value);
      persist({ wired_display_mode: value });
    },
    [persist]
  );

  // Réglage du mode d'affichage câblé : "auto" (dérivé du matériel, défaut) ou
  // forçage manuel. En forçage, le mode effectif est appliqué tout de suite
  // localement ; en auto, le serveur le recalcule et le rediffuse.
  const setDisplayModeSetting = useCallback(
    (value: DisplayModeSetting) => {
      setDisplayModeSettingState(value);
      if (value !== "auto") setWiredDisplayModeState(value);
      persist({ display_mode_setting: value });
    },
    [persist]
  );

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => translate(language, key, params),
    [language]
  );

  const tList = useCallback((key: string) => translateList(language, key), [language]);

  // useMemo : avant l'ajout du branding/toggle, AppLogo
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
      activeLogo,
      setActiveLogo,
      logoVersion,
      refreshBranding,
      wiredDisplayMode,
      setWiredDisplayMode,
      displayModeSetting,
      setDisplayModeSetting,
      displayExternalCount,
      waitTimeBetweenCourses,
      network,
      updateChannel,
    }),
    [theme, language, t, tList, setTheme, setLanguage, hasCustomLogo, activeLogo, setActiveLogo, logoVersion, refreshBranding, wiredDisplayMode, setWiredDisplayMode, displayModeSetting, setDisplayModeSetting, displayExternalCount, waitTimeBetweenCourses, network, updateChannel]
  );

  return (
    <AppSettingsContext.Provider value={value}>
      {children}
    </AppSettingsContext.Provider>
  );
}
