"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { translate, translateList, UI_LANGUAGE, type Language } from "@/lib/i18n";
import { pushUpdateChannelToNative } from "@/lib/nativeBridge";
import { DEFAULT_RELEASE_CHANNEL, type UpdateChannel } from "@/lib/releaseChannel";
import { readBranding, readSettings, fetchSettings, persistSettings, type SettingsPatch } from "@/lib/settings/payload";
import {
  DEFAULT_LANGUAGE,
  DEFAULT_NETWORK,
  DEFAULT_WIRED_DISPLAY_MODE,
  type ActiveLogo,
  type AppSettingsContextValue,
  type DisplayModeSetting,
  type NetworkInfo,
  type Theme,
  type WiredDisplayMode,
} from "@/lib/settings/types";
import { useSettingsSocket } from "@/lib/settings/useSettingsSocket";
import { useThemeDocument } from "@/lib/settings/useThemeDocument";
import { useGlassGovernor } from "@/lib/useGlassGovernor";
import { DEFAULT_MODE, DEFAULT_THEME, resolveStored, type ThemeMode } from "@/lib/themePalettes";

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

function useSettingsState() {
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME);
  const [themeMode, setThemeMode] = useState<ThemeMode>(DEFAULT_MODE);
  const [storedLanguage, setLanguage] = useState<Language>(UI_LANGUAGE);
  const [simplifiedUi, setSimplifiedUi] = useState(false);
  const [hasCustomLogo, setHasCustomLogo] = useState(false);
  const [activeLogo, setActiveLogo] = useState<ActiveLogo>("default");
  const [logoVersion, setLogoVersion] = useState(0);
  const [wiredDisplayMode, setWiredDisplayMode] = useState<WiredDisplayMode>(DEFAULT_WIRED_DISPLAY_MODE);
  const [waitTimeBetweenCourses, setWaitTimeBetweenCourses] = useState<number>(0);
  const [displayModeSetting, setDisplayModeSetting] = useState<DisplayModeSetting>("auto");
  const [displayExternalCount, setDisplayExternalCount] = useState<number | null>(null);
  const [network, setNetwork] = useState<NetworkInfo>(DEFAULT_NETWORK);
  const [updateChannel, setUpdateChannel] = useState<UpdateChannel>(DEFAULT_RELEASE_CHANNEL);

  const apply = useCallback((patch: SettingsPatch) => {
    if (patch.theme !== undefined) setTheme(patch.theme);
    if (patch.themeMode !== undefined) setThemeMode(patch.themeMode);
    if (patch.language !== undefined) setLanguage(patch.language);
    if (patch.simplifiedUi !== undefined) setSimplifiedUi(patch.simplifiedUi);
    if (patch.hasCustomLogo !== undefined) {
      setHasCustomLogo(patch.hasCustomLogo);
      setLogoVersion((v) => v + 1);
    }
    if (patch.activeLogo !== undefined) setActiveLogo(patch.activeLogo);
    if (patch.wiredDisplayMode !== undefined) setWiredDisplayMode(patch.wiredDisplayMode);
    if (patch.updateChannel !== undefined) {
      setUpdateChannel(patch.updateChannel);
      pushUpdateChannelToNative(patch.updateChannel);
    }
    if (patch.displayModeSetting !== undefined) setDisplayModeSetting(patch.displayModeSetting);
    if ("displayExternalCount" in patch) setDisplayExternalCount(patch.displayExternalCount ?? null);
    if (patch.waitTimeBetweenCourses !== undefined) setWaitTimeBetweenCourses(patch.waitTimeBetweenCourses);
    if (patch.network !== undefined) setNetwork(patch.network);
  }, []);

  const values = React.useMemo(
    () => ({ theme, themeMode, storedLanguage, simplifiedUi, hasCustomLogo, activeLogo, logoVersion, wiredDisplayMode, waitTimeBetweenCourses, displayModeSetting, displayExternalCount, network, updateChannel }),
    [theme, themeMode, storedLanguage, simplifiedUi, hasCustomLogo, activeLogo, logoVersion, wiredDisplayMode, waitTimeBetweenCourses, displayModeSetting, displayExternalCount, network, updateChannel],
  );
  return { values, apply };
}

function useSettingsSync(apply: (patch: SettingsPatch) => void) {
  const refetch = useCallback(() => {
    fetchSettings().then((data) => data && apply(readSettings(data))).catch(() => {});
  }, [apply]);

  useEffect(() => {
    try {
      const cachedTheme = localStorage.getItem("olc-theme");
      if (cachedTheme) {
        const stored = resolveStored(cachedTheme, localStorage.getItem("olc-theme-mode"));
        apply({ theme: stored.theme, themeMode: stored.mode });
      }
    } catch {
    }
    refetch();
  }, [apply, refetch]);

  useEffect(() => {
    const id = setInterval(refetch, 15000);
    return () => clearInterval(id);
  }, [refetch]);

  useSettingsSocket({ apply, refetch });

  return useCallback(() => {
    fetchSettings().then((data) => data && apply(readBranding(data))).catch(() => {});
  }, [apply]);
}

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  useGlassGovernor();
  const { values, apply } = useSettingsState();
  const refreshBranding = useSettingsSync(apply);
  const language: Language = UI_LANGUAGE;
  const { theme, themeMode } = values;
  const resolvedMode = useThemeDocument(theme, themeMode, language, values.updateChannel);

  const setTheme = useCallback((value: Theme) => {
    apply({ theme: value });
    persistSettings({ theme: value, theme_mode: themeMode });
  }, [apply, themeMode]);
  const setThemeMode = useCallback((value: ThemeMode) => {
    apply({ themeMode: value });
    persistSettings({ theme, theme_mode: value });
  }, [apply, theme]);
  const setters = React.useMemo(() => ({
    setLanguage: (value: Language) => {
      apply({ language: value });
      persistSettings({ language: value });
    },
    setSimplifiedUi: (value: boolean) => {
      apply({ simplifiedUi: value });
      persistSettings({ simplified_ui: value ? "true" : "false" });
    },
    setActiveLogo: (value: ActiveLogo) => {
      apply({ activeLogo: value });
      persistSettings({ active_logo: value });
    },
    setWiredDisplayMode: (value: WiredDisplayMode) => {
      apply({ wiredDisplayMode: value });
      persistSettings({ wired_display_mode: value });
    },
    setDisplayModeSetting: (value: DisplayModeSetting) => {
      apply(value !== "auto" ? { displayModeSetting: value, wiredDisplayMode: value } : { displayModeSetting: value });
      persistSettings({ display_mode_setting: value });
    },
  }), [apply]);

  const t = useCallback((key: string, params?: Record<string, string | number>) => translate(key, params), []);
  const tList = useCallback((key: string) => translateList(key), []);

  const value = React.useMemo(
    () => ({
      ...values,
      ...setters,
      setTheme,
      setThemeMode,
      resolvedMode,
      language,
      languagePending: values.storedLanguage !== language,
      t,
      tList,
      refreshBranding,
    }),
    [values, setters, setTheme, setThemeMode, resolvedMode, language, t, tList, refreshBranding]
  );

  return (
    <AppSettingsContext.Provider value={value}>
      {children}
    </AppSettingsContext.Provider>
  );
}
