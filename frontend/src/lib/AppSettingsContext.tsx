"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { clearCachesAndReload } from "@/lib/cacheReload";
import { translate, translateList, UI_LANGUAGE, type Language } from "@/lib/i18n";
import { pushThemeToNative, pushUpdateChannelToNative } from "@/lib/nativeBridge";
import { applyChannelFavicon, DEFAULT_RELEASE_CHANNEL, isReleaseChannel, type UpdateChannel } from "@/lib/releaseChannel";
import { useGlassGovernor } from "@/lib/useGlassGovernor";
import {
  DEFAULT_MODE,
  DEFAULT_THEME,
  resolveMode,
  resolveStored,
  type ResolvedMode,
  type ThemeId,
  type ThemeMode,
} from "@/lib/themePalettes";

export type Theme = ThemeId;

export interface NetworkInfo {
  localIp: string | null;
  port: number;
  mdnsUrl: string;
}

export type ActiveLogo = "default" | "custom";
export type { UpdateChannel };
export type WiredDisplayMode = "dual_screen" | "headless";
/** Réglage administrateur : "auto" = dérivé des écrans externes réellement
 * connectés ; sinon forçage manuel. */
export type DisplayModeSetting = "auto" | WiredDisplayMode;

interface AppSettingsContextValue {
  theme: Theme;
  /** Choix du mode : suivre le système (« auto »), clair ou sombre. */
  themeMode: ThemeMode;
  /** Mode réellement appliqué (clair ou sombre). */
  resolvedMode: ResolvedMode;
  /** Langue de cet export (fixée à la compilation) : toujours celle des textes affichés. */
  language: Language;
  /** Langue enregistrée dans Réglages ; elle ne s'applique qu'au redémarrage suivant. */
  storedLanguage: Language;
  /** Vrai quand la langue enregistrée diffère de celle affichée : un redémarrage est requis. */
  languagePending: boolean;
  /** Interface simplifiée (M28) : masque coach, métriques et journaux. */
  simplifiedUi: boolean;
  setSimplifiedUi: (value: boolean) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  tList: (key: string) => string[];
  setTheme: (theme: Theme) => void;
  setThemeMode: (mode: ThemeMode) => void;
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
   * l'illustration affichée par AppLogo et le favicon (cf. lib/releaseChannel.ts). */
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

const DEFAULT_LANGUAGE: Language = "fr";
const DEFAULT_WIRED_DISPLAY_MODE: WiredDisplayMode = "headless";
const DEFAULT_NETWORK: NetworkInfo = { localIp: null, port: 1903, mdnsUrl: "http://bobine.local" };

const AppSettingsContext = createContext<AppSettingsContextValue>({
  theme: DEFAULT_THEME,
  themeMode: DEFAULT_MODE,
  resolvedMode: "light",
  language: UI_LANGUAGE,
  storedLanguage: DEFAULT_LANGUAGE,
  languagePending: false,
  simplifiedUi: false,
  setSimplifiedUi: () => {},
  t: (key) => key,
  tList: () => [],
  setTheme: () => {},
  setThemeMode: () => {},
  setLanguage: () => {},
  hasCustomLogo: false,
  activeLogo: "default",
  setActiveLogo: () => {},
  logoVersion: 0,
  refreshBranding: () => {},
  updateChannel: DEFAULT_RELEASE_CHANNEL,
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
  useGlassGovernor();
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [themeMode, setThemeModeState] = useState<ThemeMode>(DEFAULT_MODE);
  const [resolvedMode, setResolvedMode] = useState<ResolvedMode>("light");
  // `language` (celle des textes) est fixée par l'export ; seule la langue enregistrée évolue.
  const language: Language = UI_LANGUAGE;
  const [storedLanguage, setLanguageState] = useState<Language>(UI_LANGUAGE);
  const [simplifiedUi, setSimplifiedUiState] = useState(false);
  const [hasCustomLogo, setHasCustomLogo] = useState(false);
  const [activeLogo, setActiveLogoState] = useState<ActiveLogo>("default");
  const [logoVersion, setLogoVersion] = useState(0);
  const [wiredDisplayMode, setWiredDisplayModeState] = useState<WiredDisplayMode>(DEFAULT_WIRED_DISPLAY_MODE);
  const [waitTimeBetweenCourses, setWaitTimeBetweenCourses] = useState<number>(0);
  const [displayModeSetting, setDisplayModeSettingState] = useState<DisplayModeSetting>("auto");
  const [displayExternalCount, setDisplayExternalCount] = useState<number | null>(null);
  const [network, setNetwork] = useState<NetworkInfo>(DEFAULT_NETWORK);
  const [updateChannel, setUpdateChannel] = useState<UpdateChannel>(DEFAULT_RELEASE_CHANNEL);

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
    if (typeof data.theme === "string") {
      // Un ancien nom de thème (serveur ou sauvegarde d'avant la 5.2) donne sa couleur et son mode.
      const stored = resolveStored(data.theme, data.theme_mode);
      setThemeState(stored.theme);
      setThemeModeState(stored.mode);
    }
    if (data.language === "fr" || data.language === "en") {
      setLanguageState(data.language);
    }
    if (data.simplified_ui === "true" || data.simplified_ui === "false") {
      setSimplifiedUiState(data.simplified_ui === "true");
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
    if (isReleaseChannel(data.update_channel)) {
      setUpdateChannel(data.update_channel);
      pushUpdateChannelToNative(data.update_channel);
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
      const cachedTheme = localStorage.getItem("olc-theme");
      if (cachedTheme) {
        const stored = resolveStored(cachedTheme, localStorage.getItem("olc-theme-mode"));
        // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise l'état avec le cache localStorage au montage, même motif que le chargement initial ailleurs dans le projet (library/playlists/schedule)
        setThemeState(stored.theme);
        setThemeModeState(stored.mode);
      }
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
    // Identifiant du lancement du backend vu à la première connexion : un autre, après une reconnexion, signifie un
    // redémarrage (changement de langue appliqué, mise à jour). L'écran se recharge alors seul et reçoit l'export
    // de la langue enregistrée, comme les pages qui suivent déjà la lecture (usePlaybackSocket).
    let bootId: string | null = null;

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
          if (parsed.event === "boot_id") {
            if (bootId === null) bootId = parsed.boot_id;
            else if (bootId !== parsed.boot_id) void clearCachesAndReload();
            return;
          }
          if (parsed.event === "settings_change") {
            if (typeof parsed.theme === "string") {
              const stored = resolveStored(parsed.theme, parsed.theme_mode);
              // eslint-disable-next-line react-hooks/set-state-in-effect -- réaction à un évènement externe temps réel, pas un calcul dérivable au rendu
              setThemeState(stored.theme);
              setThemeModeState(stored.mode);
            }
            if (parsed.language === "fr" || parsed.language === "en") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setLanguageState(parsed.language);
            }
            if (parsed.simplified_ui === "true" || parsed.simplified_ui === "false") {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setSimplifiedUiState(parsed.simplified_ui === "true");
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
            if (isReleaseChannel(parsed.update_channel)) {
              // eslint-disable-next-line react-hooks/set-state-in-effect -- idem
              setUpdateChannel(parsed.update_channel);
              pushUpdateChannelToNative(parsed.update_channel);
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

  // Mode effectif : « auto » suit le réglage du système et le réévalue quand il change.
  useEffect(() => {
    const query = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    const apply = () => {
      const resolved = resolveMode(themeMode, Boolean(query?.matches));
      document.documentElement.setAttribute("data-mode", resolved);
      setResolvedMode(resolved);
    };
    apply();
    if (themeMode !== "auto" || !query) return;
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, [themeMode]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("olc-theme", theme);
      localStorage.setItem("olc-theme-mode", themeMode);
    } catch {
      // ignore
    }
    // Les variables du thème sont résolues à l'image suivante.
    const frame = requestAnimationFrame(() => requestAnimationFrame(pushThemeToNative));
    return () => cancelAnimationFrame(frame);
  }, [theme, themeMode, resolvedMode]);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  // Onglet du navigateur aux couleurs du canal choisi (cf. lib/releaseChannel.ts).
  useEffect(() => {
    applyChannelFavicon(document, updateChannel);
  }, [updateChannel]);

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
      // Paire complète : sans le mode, le serveur lit un ancien nom (chili, charbon, orchidee) comme
      // une écriture d'avant la 5.2 et écrase le mode courant.
      persist({ theme: value, theme_mode: themeMode });
    },
    [persist, themeMode]
  );

  const setThemeMode = useCallback(
    (value: ThemeMode) => {
      setThemeModeState(value);
      // Envoyer aussi la couleur résolue normalise un ancien nom stocké (ex. lavande) : le serveur ne
      // relit plus « auto » à travers le mode fixe de cet ancien thème.
      persist({ theme, theme_mode: value });
    },
    [persist, theme]
  );

  const setLanguage = useCallback(
    (value: Language) => {
      setLanguageState(value);
      persist({ language: value });
    },
    [persist]
  );

  const setSimplifiedUi = useCallback(
    (value: boolean) => {
      setSimplifiedUiState(value);
      persist({ simplified_ui: value ? "true" : "false" });
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
    (key: string, params?: Record<string, string | number>) => translate(key, params),
    []
  );

  const tList = useCallback((key: string) => translateList(key), []);

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
      themeMode,
      resolvedMode,
      language,
      storedLanguage,
      languagePending: storedLanguage !== language,
      simplifiedUi,
      setSimplifiedUi,
      t,
      tList,
      setTheme,
      setThemeMode,
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
    [theme, themeMode, resolvedMode, language, storedLanguage, simplifiedUi, setSimplifiedUi, t, tList, setTheme, setThemeMode, setLanguage, hasCustomLogo, activeLogo, setActiveLogo, logoVersion, refreshBranding, wiredDisplayMode, setWiredDisplayMode, displayModeSetting, setDisplayModeSetting, displayExternalCount, waitTimeBetweenCourses, network, updateChannel]
  );

  return (
    <AppSettingsContext.Provider value={value}>
      {children}
    </AppSettingsContext.Provider>
  );
}
