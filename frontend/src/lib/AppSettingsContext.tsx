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
import { getApiUrl, getPlaybackWsUrl } from "@/lib/apiUrl";

export type Theme = ThemeId;

export interface NetworkInfo {
  localIp: string | null;
  port: number;
  mdnsUrl: string;
}

export type ActiveLogo = "default" | "custom";
export type { UpdateChannel };
export type WiredDisplayMode = "dual_screen" | "headless";
export type DisplayModeSetting = "auto" | WiredDisplayMode;

interface AppSettingsContextValue {
  theme: Theme;
  themeMode: ThemeMode;
  resolvedMode: ResolvedMode;
  language: Language;
  storedLanguage: Language;
  languagePending: boolean;
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
  logoVersion: number;
  refreshBranding: () => void;
  updateChannel: UpdateChannel;
  wiredDisplayMode: WiredDisplayMode;
  setWiredDisplayMode: (mode: WiredDisplayMode) => void;
  displayModeSetting: DisplayModeSetting;
  setDisplayModeSetting: (setting: DisplayModeSetting) => void;
  displayExternalCount: number | null;
  waitTimeBetweenCourses: number;
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

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  useGlassGovernor();
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [themeMode, setThemeModeState] = useState<ThemeMode>(DEFAULT_MODE);
  const [resolvedMode, setResolvedMode] = useState<ResolvedMode>("light");
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

  const applySettingsPayload = useCallback((data: Record<string, unknown> | null) => {
    if (!data) return;
    if (typeof data.theme === "string") {
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
    }

    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then(applySettingsPayload)
      .catch(() => {});
  }, [applySettingsPayload]);

  useEffect(() => {
    const id = setInterval(() => {
      fetch(getApiUrl("/settings"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then(applySettingsPayload)
        .catch(() => {});
    }, 15000);
    return () => clearInterval(id);
  }, [applySettingsPayload]);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let bootId: string | null = null;

    const connect = () => {
      if (cancelled || typeof window === "undefined") return;
      ws = new WebSocket(getPlaybackWsUrl());
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
              setThemeState(stored.theme);
              setThemeModeState(stored.mode);
            }
            if (parsed.language === "fr" || parsed.language === "en") {
              setLanguageState(parsed.language);
            }
            if (parsed.simplified_ui === "true" || parsed.simplified_ui === "false") {
              setSimplifiedUiState(parsed.simplified_ui === "true");
            }
            if (typeof parsed.has_custom_logo === "boolean") {
              setHasCustomLogo(parsed.has_custom_logo);
              setLogoVersion((v) => v + 1);
            }
            if (parsed.active_logo === "default" || parsed.active_logo === "custom") {
              setActiveLogoState(parsed.active_logo);
            }
            if (parsed.wired_display_mode === "dual_screen" || parsed.wired_display_mode === "headless") {
              setWiredDisplayModeState(parsed.wired_display_mode);
            }
            if (isReleaseChannel(parsed.update_channel)) {
              setUpdateChannel(parsed.update_channel);
              pushUpdateChannelToNative(parsed.update_channel);
            }
          }
          if (parsed.event === "display_mode_change") {
            const mode = parsed.mode || parsed.wired_display_mode;
            if (mode === "dual_screen" || mode === "headless") {
              setWiredDisplayModeState(mode);
            }
            fetch(getApiUrl("/settings"), { cache: "no-store" })
              .then((res) => (res.ok ? res.json() : null))
              .then(applySettingsPayload)
              .catch(() => {});
          }
        } catch {
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
    }
    const frame = requestAnimationFrame(() => requestAnimationFrame(pushThemeToNative));
    return () => cancelAnimationFrame(frame);
  }, [theme, themeMode, resolvedMode]);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

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
      persist({ theme: value, theme_mode: themeMode });
    },
    [persist, themeMode]
  );

  const setThemeMode = useCallback(
    (value: ThemeMode) => {
      setThemeModeState(value);
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
