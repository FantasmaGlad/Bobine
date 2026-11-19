"use client";

import Icon from "@/components/Icon";

export default function SettingsSearch({ query, setQuery, placeholder }: { query: string; setQuery: (value: string) => void; placeholder: string }) {
  return (
    <div className="settings-search-row">
      <label className="settings-search">
        <Icon name="search" size={18} />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
        />
      </label>
    </div>
  );
}
