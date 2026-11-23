"use client";

import Icon from "@/components/Icon";
import { SETTINGS_GROUPS, type SettingsCategory, type SettingsCategoryId } from "@/lib/settingsCategories";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export default function SettingsTree({ categories, active, onChoose, search, t }: {
  categories: readonly SettingsCategory[]; active: SettingsCategoryId | null; onChoose: (id: SettingsCategoryId) => void;
  search: React.ReactNode; t: Translate;
}) {
  return (
    <nav className="settings-tree" aria-label={t("settingsPage.categoriesLabel")}>
      {search}
      {SETTINGS_GROUPS.map((group) => (
        <div key={group} className="settings-tree-group">
          <span className="settings-tree-title">{t(`settingsPage.groups.${group}`)}</span>
          <ul>
            {categories.filter((category) => category.group === group).map((category) => (
              <li key={category.id}>
                <button type="button" className={`settings-tree-item${active === category.id ? " is-active" : ""}`}
                  aria-current={active === category.id ? "page" : undefined} onClick={() => onChoose(category.id)}>
                  <Icon name={category.icon} size={18} />
                  <span>{t(`settingsPage.cat.${category.id}.label`)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
