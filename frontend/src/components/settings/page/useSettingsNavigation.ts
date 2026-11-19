"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_SETTINGS_CATEGORY, categoryOfSection, matchCategories, type SettingsCategoryId } from "@/lib/settingsCategories";
import { useClientSnapshot } from "@/lib/useClientSnapshot";

type Translate = (key: string) => string;

export function useSettingsNavigation(t: Translate) {
  const linkedSection = useClientSnapshot(() => window.location.hash.replace(/^#/, ""), "");
  const [chosenCategory, setCategory] = useState<SettingsCategoryId | null>(null);
  const category = chosenCategory ?? categoryOfSection(linkedSection) ?? DEFAULT_SETTINGS_CATEGORY;
  const [query, setQuery] = useState("");
  const searching = query.trim().length > 0;
  const matched = useMemo(
    () => matchCategories(query, (id) => ["label", "desc", "keywords"].map((part) => t(`settingsPage.cat.${id}.${part}`)).join(" ")),
    [query, t],
  );
  const shows = (sectionId: string) => {
    const owner = categoryOfSection(sectionId);
    return searching ? owner !== undefined && matched.has(owner) : owner === category;
  };
  const chooseCategory = (id: SettingsCategoryId) => {
    setQuery("");
    setCategory(id);
  };
  const openSection = useCallback((sectionId: string) => {
    const owner = categoryOfSection(sectionId);
    if (owner) {
      setQuery("");
      setCategory(owner);
    }
    window.setTimeout(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }, []);
  useEffect(() => {
    if (!linkedSection || !categoryOfSection(linkedSection)) return;
    window.setTimeout(() => document.getElementById(linkedSection)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }, [linkedSection]);

  return { category, query, setQuery, searching, matched, shows, chooseCategory, openSection };
}
