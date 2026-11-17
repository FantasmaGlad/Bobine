import type { Language } from "@/lib/i18n";
import type { UpdateChannel } from "@/lib/releaseChannel";
import type { ResolvedMode, ThemeId, ThemeMode } from "@/lib/themePalettes";

export type Theme = ThemeId;

export interface NetworkInfo {
  localIp: string | null;
  port: number;
  mdnsUrl: string;
}

export type ActiveLogo = "default" | "custom";
export type WiredDisplayMode = "dual_screen" | "headless";
export type DisplayModeSetting = "auto" | WiredDisplayMode;

export interface AppSettingsContextValue {
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

export const DEFAULT_LANGUAGE: Language = "fr";
export const DEFAULT_WIRED_DISPLAY_MODE: WiredDisplayMode = "headless";
export const DEFAULT_NETWORK: NetworkInfo = { localIp: null, port: 1903, mdnsUrl: "http://bobine.local" };
