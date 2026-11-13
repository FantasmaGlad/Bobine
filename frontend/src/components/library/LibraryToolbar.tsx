"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SearchBox from "@/components/SearchBox";
import { useAppSettings } from "@/lib/AppSettingsContext";

export interface LibraryFilters {
  search: string;
  program: string;
  release: string;
  sortBy: string;
}

interface Props {
  filters: LibraryFilters;
  onChange: (patch: Partial<LibraryFilters>) => void;
  programs: string[];
  suggestions: string[];
  viewMode: "grid" | "list";
  onViewMode: (mode: "grid" | "list") => void;
}

function ViewToggle({ viewMode, onViewMode }: Pick<Props, "viewMode" | "onViewMode">) {
  const { t } = useAppSettings();
  return (
    <div className="view-toggle">
      <button className={`view-btn olc-press ${viewMode === "grid" ? "active" : ""}`} onClick={() => onViewMode("grid")} title={t("library.gridView")}>
        <Icon name="grid_view" size={18} />
      </button>
      <button className={`view-btn olc-press ${viewMode === "list" ? "active" : ""}`} onClick={() => onViewMode("list")} title={t("library.listView")}>
        <Icon name="view_list" size={18} />
      </button>
    </div>
  );
}

export default function LibraryToolbar({ filters, onChange, programs, suggestions, viewMode, onViewMode }: Props) {
  const { t } = useAppSettings();
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  return (
    <div className="library-toolbar sticky-glass-toolbar">
      <div className="toolbar-filters">
        <SearchBox
          className="search-input"
          placeholder={t("library.searchPlaceholder")}
          value={filters.search}
          onChange={(search) => onChange({ search })}
          suggestions={suggestions}
        />
        <button
          type="button"
          className={`btn btn-secondary mobile-filter-toggle-btn ${mobileFiltersOpen ? "active" : ""}`}
          style={{ padding: "8px 12px", fontSize: "0.82rem" }}
          aria-expanded={mobileFiltersOpen}
          aria-label={t("library.filters")}
          onClick={() => setMobileFiltersOpen((v) => !v)}
        >
          <Icon name="tune" size={18} />
        </button>
        <div className={`toolbar-secondary-filters ${mobileFiltersOpen ? "open" : ""}`}>
          <ResponsiveSelect
            value={filters.program}
            onChange={(program) => onChange({ program })}
            placeholder={t("library.allPrograms")}
            title={t("library.allPrograms")}
            options={programs.map((p) => ({ value: p, label: p }))}
          />
          <input
            type="text"
            className="search-input"
            style={{ width: "120px" }}
            placeholder={t("library.releasePlaceholder")}
            value={filters.release}
            onChange={(e) => onChange({ release: e.target.value })}
          />
          <ResponsiveSelect
            value={filters.sortBy}
            onChange={(sortBy) => onChange({ sortBy })}
            title={t("library.sortImportDate")}
            options={[
              { value: "imported_at", label: t("library.sortImportDate") },
              { value: "title", label: t("library.sortTitle") },
              { value: "duration", label: t("library.sortDuration") },
            ]}
          />
        </div>
      </div>
      <ViewToggle viewMode={viewMode} onViewMode={onViewMode} />
    </div>
  );
}
