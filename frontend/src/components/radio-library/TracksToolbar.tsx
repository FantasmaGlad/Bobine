"use client";

import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SearchBox from "@/components/SearchBox";
import { useAppSettings } from "@/lib/AppSettingsContext";

import type { SortKey, ViewMode } from "./types";
import { filterIcon, type TrackFilter } from "./useTrackFilter";

interface Props {
  filter: TrackFilter;
  viewMode: ViewMode;
  onViewMode: (mode: ViewMode) => void;
  allSelected: boolean;
  onToggleAll: () => void;
}

const SORTS: SortKey[] = ["recent", "title", "artist", "duration"];
const SORT_LABELS: Record<SortKey, string> = { recent: "radioLibrary.sortRecent", title: "radioLibrary.sortTitle", artist: "radioLibrary.sortArtist", duration: "radioLibrary.sortDuration" };

function ViewToggle({ viewMode, onViewMode }: Pick<Props, "viewMode" | "onViewMode">) {
  const { t } = useAppSettings();
  const button = (mode: ViewMode, icon: string, title: string) => (
    <button type="button" className={`view-btn ${viewMode === mode ? "active" : ""}`} onClick={() => onViewMode(mode)} title={t(title)} aria-pressed={viewMode === mode}>
      <Icon name={icon} size={16} />
    </button>
  );
  return (
    <div className="view-toggle" role="group" aria-label={t("radioLibrary.viewLabel")}>
      {button("grid", "grid_view", "radioLibrary.viewGrid")}
      {button("list", "view_list", "radioLibrary.viewList")}
    </div>
  );
}

export default function TracksToolbar({ filter, viewMode, onViewMode, allSelected, onToggleAll }: Props) {
  const { t } = useAppSettings();
  const count = filter.sorted.length;
  return (
    <div className="rl-toolbar sticky-glass-toolbar">
      <div className="rl-search-wrap">
        <SearchBox className="search-input rl-search" placeholder={t("radioLibrary.searchPlaceholder")} value={filter.search} onChange={filter.setSearch} suggestions={filter.suggestions} />
      </div>
      {filter.filter && (
        <div className="rl-filter-chip">
          <Icon name={filterIcon(filter.filter)} size={16} />
          <span>{filter.filter.value}</span>
          <button type="button" onClick={filter.clear} title={t("radioLibrary.clearFilter")}><Icon name="close" size={14} /></button>
        </div>
      )}
      <span className="rl-count">{t("radioLibrary.countLabel", { count })}</span>
      <div className="rl-toolbar-spacer" />
      <ResponsiveSelect
        className="filter-select"
        value={filter.sortKey}
        onChange={(value) => filter.setSortKey(value as SortKey)}
        title={t("radioLibrary.sortLabel")}
        searchable={false}
        options={SORTS.map((value) => ({ value, label: t(SORT_LABELS[value]) }))}
      />
      <ViewToggle viewMode={viewMode} onViewMode={onViewMode} />
      {count > 0 && (
        <button type="button" className="btn btn-secondary" onClick={onToggleAll}>
          <Icon name="checklist" size={16} /> {allSelected ? t("radioLibrary.deselectAll") : t("radioLibrary.selectAll")}
        </button>
      )}
    </div>
  );
}
