"use client";

import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import OptionBody from "@/components/select/OptionBody";
import OptionRows from "@/components/select/OptionRows";
import { listKeyHandler } from "@/components/select/listKeyboard";
import { groupOptions, searchTextOf, type SelectOption } from "@/components/select/options";
import { POPOVER_MAX_HEIGHT, usePopoverAnchor } from "@/components/select/usePopoverAnchor";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { rankByQuery } from "@/lib/searchText";
import { useIsMobile } from "@/lib/useIsMobile";

interface ResponsiveSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
  disabled?: boolean;
  searchable?: boolean;
}

function useFlatRows(options: SelectOption[], query: string, placeholder: string | undefined) {
  const hasEmptyEntry = placeholder !== undefined && !query;
  const visible = useMemo(() => rankByQuery(options, query, searchTextOf), [options, query]);
  const flat = useMemo(() => {
    const rows: SelectOption[] = [];
    if (hasEmptyEntry) rows.push({ value: "", label: placeholder ?? "" });
    for (const [, items] of groupOptions(visible)) rows.push(...items);
    return rows;
  }, [visible, hasEmptyEntry, placeholder]);
  return { hasEmptyEntry, visible, flat };
}

export default function ResponsiveSelect({
  value, onChange, options, placeholder, title, className = "filter-select", style, disabled, searchable,
}: ResponsiveSelectProps) {
  const isMobile = useIsMobile();
  const { t } = useAppSettings();
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const selected = options.find((option) => option.value === value);
  const showSearch = searchable ?? options.length > 4;
  const { hasEmptyEntry, visible, flat } = useFlatRows(options, query, placeholder);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);
  const anchor = usePopoverAnchor(open && !isMobile, triggerRef, popoverRef, close);

  const choose = (next: string) => {
    onChange(next);
    close();
    triggerRef.current?.focus();
  };

  const openList = () => {
    if (disabled) return;
    const index = flat.findIndex((row) => row.value === value);
    setActiveIndex(index >= 0 ? index : 0);
    setOpen(true);
  };

  useEffect(() => {
    if (open && anchor && !showSearch && !isMobile) listRef.current?.focus();
  }, [open, anchor, showSearch, isMobile]);

  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelector<HTMLElement>(`[data-row="${activeIndex}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, activeIndex]);

  const handleKeyDown = (event: React.KeyboardEvent) => listKeyHandler({
    count: flat.length,
    setActive: setActiveIndex,
    chooseActive: () => {
      const row = flat[activeIndex];
      if (row) choose(row.value);
    },
    dismiss: () => {
      close();
      triggerRef.current?.focus();
    },
    close,
  })(event);

  const rows = (
    <OptionRows
      listId={listId} value={value} visible={visible} query={query} placeholder={placeholder} hasEmptyEntry={hasEmptyEntry}
      activeIndex={activeIndex} emptyLabel={t("mobileRemote.noResults")} onActivate={setActiveIndex} onChoose={choose}
    />
  );

  const searchField = showSearch ? (
    <input
      type="search"
      role="combobox"
      aria-expanded
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={flat.length > 0 ? `${listId}-${activeIndex}` : undefined}
      className="search-input sheet-search"
      placeholder={t("mobileRemote.searchPlaceholder")}
      aria-label={t("mobileRemote.searchPlaceholder")}
      value={query}
      onChange={(event) => {
        setQuery(event.target.value);
        setActiveIndex(0);
      }}
      onKeyDown={handleKeyDown}
      autoFocus
      autoComplete="off"
      autoCorrect="off"
      spellCheck={false}
      enterKeyHint="search"
    />
  ) : null;

  const trigger = (
    <button
      ref={triggerRef}
      type="button"
      className={`select-trigger rs-trigger ${className}${selected?.thumbnail ? " has-preview" : ""}`}
      style={style}
      disabled={disabled}
      title={title}
      onClick={() => (open ? close() : openList())}
      onKeyDown={(event) => {
        if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
          event.preventDefault();
          openList();
        } else if (open && event.key !== "Enter" && event.key !== " ") {
          handleKeyDown(event);
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

  if (isMobile) {
    return (
      <>
        {trigger}
        <Sheet open={open} onClose={close} title={title ?? placeholder} tall={options.length > 6} closeLabel={t("mobileRemote.close")} header={searchField ?? undefined}>
          <div ref={listRef} id={listId} role="listbox" className="rs-list">
            {rows}
          </div>
        </Sheet>
      </>
    );
  }

  return (
    <>
      {trigger}
      {open && anchor && typeof document !== "undefined" && createPortal(
        <div
          ref={popoverRef}
          className="rs-popover glass-floating"
          style={{
            position: "fixed",
            left: anchor.left,
            width: anchor.width,
            maxHeight: POPOVER_MAX_HEIGHT,
            ...(anchor.above ? { bottom: window.innerHeight - anchor.top } : { top: anchor.top }),
          }}
          onKeyDown={handleKeyDown}
        >
          {searchField ? <div className="rs-popover__search">{searchField}</div> : null}
          <div ref={listRef} id={listId} role="listbox" className="rs-list" tabIndex={searchField ? -1 : 0}>
            {rows}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
