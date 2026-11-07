/**
 * Catégories de la page Réglages : chaque section (identifiant HTML) appartient à une seule catégorie, la page n'affiche
 * que la catégorie choisie, et la recherche retrouve une catégorie par son nom, sa description ou ses mots-clés.
 * Module pur (aucun accès au DOM) : testable seul (`tests/settingsCategories.test.ts`).
 */

export type SettingsCategoryId = "appearance" | "display" | "playback" | "updates" | "data" | "system" | "help" | "danger";

export interface SettingsCategory {
  id: SettingsCategoryId;
  /** Icône Material Symbols. */
  icon: string;
  /** Identifiants des sections de la page qui composent la catégorie. */
  sections: readonly string[];
}

export const SETTINGS_CATEGORIES: readonly SettingsCategory[] = [
  { id: "appearance", icon: "palette", sections: ["section-appearance", "section-branding"] },
  { id: "display", icon: "tv", sections: ["section-display"] },
  { id: "playback", icon: "play_circle", sections: ["section-playback"] },
  { id: "updates", icon: "system_update", sections: ["updates-section"] },
  { id: "data", icon: "archive", sections: ["section-backup", "section-sync", "section-logs", "section-diagnostics"] },
  { id: "system", icon: "settings_power", sections: ["section-startup"] },
  { id: "help", icon: "description", sections: ["section-docs"] },
  { id: "danger", icon: "warning", sections: ["section-danger"] },
];

export const DEFAULT_SETTINGS_CATEGORY: SettingsCategoryId = "appearance";

export function categoryOfSection(sectionId: string): SettingsCategoryId | undefined {
  return SETTINGS_CATEGORIES.find((category) => category.sections.includes(sectionId))?.id;
}

/** Minuscules sans accents : « Écran » et « ecran » se retrouvent. */
export function normalizeSearch(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/**
 * Catégories qui répondent à la recherche : chaque mot saisi doit figurer dans le nom, la description ou les mots-clés
 * (`haystack` fournit ce texte, déjà traduit). Une recherche vide ne retient rien (la page affiche alors la catégorie choisie).
 */
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
