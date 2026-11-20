"use client";

import React from "react";
import Icon from "@/components/Icon";
import OptionBody from "@/components/select/OptionBody";
import { type SelectOption } from "@/components/select/options";

interface SearchProps {
  listId: string;
  hasRows: boolean;
  activeIndex: number;
  placeholder: string;
  query: string;
  onQuery: (query: string) => void;
  onKeyDown: (event: React.KeyboardEvent) => void;
}

export function SelectSearchField({ listId, hasRows, activeIndex, placeholder, query, onQuery, onKeyDown }: SearchProps) {
  return (
    <input
      type="search"
      role="combobox"
      aria-expanded
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={hasRows ? `${listId}-${activeIndex}` : undefined}
      className="search-input sheet-search"
      placeholder={placeholder}
      aria-label={placeholder}
      value={query}
      onChange={(event) => onQuery(event.target.value)}
      onKeyDown={onKeyDown}
      autoFocus
      autoComplete="off"
      autoCorrect="off"
      spellCheck={false}
      enterKeyHint="search"
    />
  );
}

interface TriggerProps {
  triggerRef: React.RefObject<HTMLButtonElement | null>;
  selected: SelectOption | undefined;
  className: string;
  style?: React.CSSProperties;
  disabled?: boolean;
  title?: string;
  placeholder?: string;
  open: boolean;
  onToggle: () => void;
  onOpen: () => void;
  onListKey: (event: React.KeyboardEvent) => void;
}

export function SelectTrigger({ triggerRef, selected, className, style, disabled, title, placeholder, open, onToggle, onOpen, onListKey }: TriggerProps) {
  return (
    <button
      ref={triggerRef}
      type="button"
      className={`select-trigger rs-trigger ${className}${selected?.thumbnail ? " has-preview" : ""}`}
      style={style}
      disabled={disabled}
      title={title}
      onClick={onToggle}
      onKeyDown={(event) => {
        if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
          event.preventDefault();
          onOpen();
        } else if (open && event.key !== "Enter" && event.key !== " ") {
          onListKey(event);
        }
      }}
      aria-haspopup="listbox"
      aria-expanded={open}
    >
      {selected ? (
        <span className="rs-trigger__selected">
          <OptionBody option={selected} />
        </span>
      ) : (
        <span className="select-trigger__label is-placeholder">{placeholder ?? ""}</span>
      )}
      <Icon name="expand_more" size={20} />
    </button>
  );
}
