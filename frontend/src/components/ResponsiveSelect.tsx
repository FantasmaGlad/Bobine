"use client";

import React, { useId } from "react";
import { createPortal } from "react-dom";
import Sheet from "@/components/Sheet";
import OptionRows from "@/components/select/OptionRows";
import { type SelectOption } from "@/components/select/options";
import { SelectSearchField, SelectTrigger } from "@/components/select/SelectParts";
import { POPOVER_MAX_HEIGHT } from "@/components/select/usePopoverAnchor";
import { useSelectState } from "@/components/select/useSelectState";
import { useAppSettings } from "@/lib/AppSettingsContext";
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

export default function ResponsiveSelect({
  value, onChange, options, placeholder, title, className = "filter-select", style, disabled, searchable,
}: ResponsiveSelectProps) {
  const isMobile = useIsMobile();
  const { t } = useAppSettings();
  const listId = useId();
  const showSearch = searchable ?? options.length > 4;
  const state = useSelectState({ value, onChange, options, placeholder, disabled, showSearch, isMobile });
  const { open, query, setQuery, activeIndex, setActiveIndex, triggerRef, popoverRef, listRef, flat, close, anchor, openList, handleKeyDown } = state;
  const selected = options.find((option) => option.value === value);

  const rows = (
    <OptionRows
      listId={listId} value={value} visible={state.visible} query={query} placeholder={placeholder} hasEmptyEntry={state.hasEmptyEntry}
      activeIndex={activeIndex} emptyLabel={t("mobileRemote.noResults")} onActivate={setActiveIndex} onChoose={state.choose}
    />
  );
  const searchField = showSearch ? (
    <SelectSearchField
      listId={listId} hasRows={flat.length > 0} activeIndex={activeIndex} placeholder={t("mobileRemote.searchPlaceholder")} query={query}
      onQuery={(next) => { setQuery(next); setActiveIndex(0); }} onKeyDown={handleKeyDown}
    />
  ) : null;
  const trigger = (
    <SelectTrigger
      triggerRef={triggerRef} selected={selected} className={className} style={style} disabled={disabled} title={title} placeholder={placeholder}
      open={open} onToggle={() => (open ? close() : openList())} onOpen={openList} onListKey={handleKeyDown}
    />
  );

  if (isMobile) {
    return (
      <>
        {trigger}
        <Sheet open={open} onClose={close} title={title ?? placeholder} tall={options.length > 6} closeLabel={t("mobileRemote.close")} header={searchField ?? undefined}>
          <div ref={listRef} id={listId} role="listbox" className="rs-list">{rows}</div>
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
          <div ref={listRef} id={listId} role="listbox" className="rs-list" tabIndex={searchField ? -1 : 0}>{rows}</div>
        </div>,
        document.body,
      )}
    </>
  );
}
