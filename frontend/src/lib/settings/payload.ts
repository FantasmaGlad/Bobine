import { getApiUrl } from "@/lib/apiUrl";
import type { Language } from "@/lib/i18n";
import { isReleaseChannel, type UpdateChannel } from "@/lib/releaseChannel";
import { resolveStored, type ThemeId, type ThemeMode } from "@/lib/themePalettes";
import { DEFAULT_NETWORK, type ActiveLogo, type DisplayModeSetting, type NetworkInfo, type WiredDisplayMode } from "./types";

export interface SettingsPatch {
  theme?: ThemeId;
  themeMode?: ThemeMode;
  language?: Language;
  simplifiedUi?: boolean;
  hasCustomLogo?: boolean;
  activeLogo?: ActiveLogo;
  wiredDisplayMode?: WiredDisplayMode;
  updateChannel?: UpdateChannel;
  displayModeSetting?: DisplayModeSetting;
  displayExternalCount?: number | null;
  waitTimeBetweenCourses?: number;
  network?: NetworkInfo;
  logoChanged?: boolean;
}

type Raw = Record<string, unknown>;

export function readBranding(data: Raw): SettingsPatch {
  const patch: SettingsPatch = {};
  if (typeof data.has_custom_logo === "boolean") patch.hasCustomLogo = data.has_custom_logo;
  if (data.active_logo === "default" || data.active_logo === "custom") patch.activeLogo = data.active_logo;
  return patch;
}

export function readLook(data: Raw): SettingsPatch {
  const patch: SettingsPatch = {};
  if (typeof data.theme === "string") {
    const stored = resolveStored(data.theme, data.theme_mode);
    patch.theme = stored.theme;
    patch.themeMode = stored.mode;
  }
  if (data.language === "fr" || data.language === "en") patch.language = data.language;
  if (data.simplified_ui === "true" || data.simplified_ui === "false") patch.simplifiedUi = data.simplified_ui === "true";
  Object.assign(patch, readBranding(data));
  if (data.wired_display_mode === "dual_screen" || data.wired_display_mode === "headless") patch.wiredDisplayMode = data.wired_display_mode;
  if (isReleaseChannel(data.update_channel)) patch.updateChannel = data.update_channel;
  return patch;
}

function readNetwork(value: unknown): NetworkInfo {
  const net = value as { local_ip?: string | null; port?: number; mdns_url?: string };
  return {
    localIp: typeof net.local_ip === "string" ? net.local_ip : null,
    port: typeof net.port === "number" ? net.port : DEFAULT_NETWORK.port,
    mdnsUrl: typeof net.mdns_url === "string" ? net.mdns_url : DEFAULT_NETWORK.mdnsUrl,
  };
}

export function readSettings(data: Raw): SettingsPatch {
  const patch = readLook(data);
  if (data.display_mode_setting === "auto" || data.display_mode_setting === "dual_screen" || data.display_mode_setting === "headless") {
    patch.displayModeSetting = data.display_mode_setting;
  }
  patch.displayExternalCount = typeof data.display_external_count === "number" ? data.display_external_count : null;
  if (typeof data.wait_time_between_courses === "number") patch.waitTimeBetweenCourses = data.wait_time_between_courses;
  if (data.network && typeof data.network === "object") patch.network = readNetwork(data.network);
  return patch;
}

export function fetchSettings(): Promise<Raw | null> {
  return fetch(getApiUrl("/settings"), { cache: "no-store" }).then((res) => (res.ok ? res.json() : null));
}

export function persistSettings(payload: Record<string, string | boolean>): void {
  fetch(getApiUrl("/settings"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => {});
}
