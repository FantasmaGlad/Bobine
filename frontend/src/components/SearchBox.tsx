"use client";

import React, { useId, useMemo, useState } from "react";
import Highlight from "@/components/Highlight";
import { useSuggestionKeys } from "@/components/search/useSuggestionKeys";
import { suggestFrom } from "@/lib/searchText";

interface SearchBoxProps {
  value: string;
  onChange: (value: string) => void;
  suggestions?: readonly string[];
  placeholder?: string;
  ariaLabel?: string;
  className?: string;
  style?: React.CSSProperties;
  autoFocus?: boolean;
  onSubmit?: (value: string) => void;
  limit?: number;
}

export default function SearchBox({
  value,
  onChange,
  suggestions,
  placeholder,
  ariaLabel,
  className = "search-input",
  style,
  autoFocus,
  onSubmit,
  limit = 6,
}: SearchBoxProps) {
  const listId = useId();
  const [focused, setFocused] = useState(false);
  const list = useMemo(() => (suggestions ? suggestFrom(suggestions, value, limit) : []), [suggestions, value, limit]);
  const { open, activeIndex, setActive, pick, handleKeyDown, typed } = useSuggestionKeys({ value, list, focused, onChange, onSubmit });

  return (
    <div className="search-box" style={{ position: "relative", width: "100%" }}>
      <input
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
        aria-label={ariaLabel ?? placeholder}
        className={className}
        style={{ width: "100%", ...style }}
        placeholder={placeholder}
        value={value}
        autoFocus={autoFocus}
        autoComplete="off"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="search"
        onChange={(event) => {
          typed();
          onChange(event.target.value);
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onKeyDown={handleKeyDown}
      />
      {open && (
        <ul id={listId} role="listbox" className="search-suggestions">
          {list.map((text, index) => (
            <li
              key={text}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              className={`search-suggestion${index === activeIndex ? " is-active" : ""}`}
              onMouseDown={(event) => {
                event.preventDefault();
                pick(text);
              }}
              onMouseEnter={() => setActive(index)}
            >
              <Highlight text={text} query={value} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
