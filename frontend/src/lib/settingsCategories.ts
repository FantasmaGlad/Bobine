export type SettingsCategoryId = "appearance" | "display" | "inputs" | "playback" | "sound" | "updates" | "data" | "system" | "help" | "danger";

export type SettingsGroupId = "general" | "playback" | "system";

export const SETTINGS_GROUPS: readonly SettingsGroupId[] = ["general", "playback", "system"];

export type SettingsCapability = "nativeBridge";

export interface SettingsCategory {
  id: SettingsCategoryId;
  group: SettingsGroupId;
  icon: string;
  sections: readonly string[];
  requires?: SettingsCapability;
}

export const SETTINGS_CATEGORIES: readonly SettingsCategory[] = [
  { id: "appearance", group: "general", icon: "palette", sections: ["section-appearance", "section-branding"] },
  { id: "display", group: "general", icon: "tv", sections: ["section-display"] },
  { id: "inputs", group: "general", icon: "sports_esports", sections: ["section-inputs"] },
  { id: "playback", group: "playback", icon: "play_circle", sections: ["section-playback"] },
  { id: "sound", group: "playback", icon: "graphic_eq", sections: ["section-sound"] },
  { id: "updates", group: "system", icon: "system_update", sections: ["updates-section"] },
  { id: "system", group: "system", icon: "settings_power", sections: ["section-startup"], requires: "nativeBridge" },
  { id: "data", group: "system", icon: "archive", sections: ["section-backup", "section-sync", "section-logs", "section-diagnostics"] },
  { id: "help", group: "system", icon: "description", sections: ["section-docs"] },
  { id: "danger", group: "system", icon: "warning", sections: ["section-danger"] },
];

export function availableCategories(capabilities: ReadonlySet<SettingsCapability>): readonly SettingsCategory[] {
  return SETTINGS_CATEGORIES.filter((category) => !category.requires || capabilities.has(category.requires));
}

export const DEFAULT_SETTINGS_CATEGORY: SettingsCategoryId = "appearance";

export function categoryOfSection(sectionId: string): SettingsCategoryId | undefined {
  return SETTINGS_CATEGORIES.find((category) => category.sections.includes(sectionId))?.id;
}

export function normalizeSearch(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

export function matchCategories(query: string, haystack: (id: SettingsCategoryId) => string): Set<SettingsCategoryId> {
  const words = normalizeSearch(query).split(/\s+/).filter(Boolean);
  const found = new Set<SettingsCategoryId>();
  if (words.length === 0) return found;
  for (const category of SETTINGS_CATEGORIES) {
    const text = normalizeSearch(haystack(category.id));
    if (words.every((word) => text.includes(word))) found.add(category.id);
  }
  return found;
}
