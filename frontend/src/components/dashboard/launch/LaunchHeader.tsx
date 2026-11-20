import SearchBox from "@/components/SearchBox";
import { type LaunchTab } from "./LaunchLists";

type T = (key: string, vars?: Record<string, string | number>) => string;

interface HeaderProps {
  search: string;
  onSearch: (value: string) => void;
  suggestions: string[];
  tab: LaunchTab;
  onTab: (tab: LaunchTab) => void;
  counts: Record<LaunchTab, number>;
  t: T;
}

export default function LaunchHeader({ search, onSearch, suggestions, tab, onTab, counts, t }: HeaderProps) {
  const tabs = [
    ["videos", t("mobileRemote.tabCourses")],
    ["playlists", t("mobileRemote.tabPlaylists")],
    ["backgrounds", t("mobileRemote.tabBackgrounds")],
  ] as const;
  return (
    <>
      <SearchBox
        className="search-input sheet-search"
        placeholder={t("mobileRemote.searchPlaceholder")}
        value={search}
        onChange={onSearch}
        suggestions={suggestions}
      />
      <div className="view-toggle launch-tabs" style={{ marginTop: 10 }}>
        {tabs.map(([key, label]) => (
          <button key={key} type="button" className={`view-btn olc-press ${tab === key ? "active" : ""}`} onClick={() => onTab(key)}>
            {label} <span style={{ opacity: 0.6 }}>{counts[key]}</span>
          </button>
        ))}
      </div>
    </>
  );
}
