import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { listKeyHandler } from "@/components/select/listKeyboard";
import { groupOptions, searchTextOf, type SelectOption } from "@/components/select/options";
import { usePopoverAnchor, type PopoverAnchor } from "@/components/select/usePopoverAnchor";
import { rankByQuery } from "@/lib/searchText";

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

interface ListFocus {
  open: boolean;
  anchor: PopoverAnchor | null;
  showSearch: boolean;
  isMobile: boolean;
  activeIndex: number;
}

function useListFocus({ open, anchor, showSearch, isMobile, activeIndex }: ListFocus, listRef: RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    if (open && anchor && !showSearch && !isMobile) listRef.current?.focus();
  }, [open, anchor, showSearch, isMobile, listRef]);

  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelector<HTMLElement>(`[data-row="${activeIndex}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, activeIndex, listRef]);
}

interface Options {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  showSearch: boolean;
  isMobile: boolean;
}

export function useSelectState({ value, onChange, options, placeholder, disabled, showSearch, isMobile }: Options) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const { hasEmptyEntry, visible, flat } = useFlatRows(options, query, placeholder);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);
  const anchor: PopoverAnchor | null = usePopoverAnchor(open && !isMobile, triggerRef, popoverRef, close);
  useListFocus({ open, anchor, showSearch, isMobile, activeIndex }, listRef);

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
  const handleKeyDown = (event: React.KeyboardEvent) => listKeyHandler({
    count: flat.length,
    setActive: setActiveIndex,
    chooseActive: () => { const row = flat[activeIndex]; if (row) choose(row.value); },
    dismiss: () => { close(); triggerRef.current?.focus(); },
    close,
  })(event);

  return {
    open, query, setQuery, activeIndex, setActiveIndex, triggerRef, popoverRef, listRef,
    hasEmptyEntry, visible, flat, close, anchor, choose, openList, handleKeyDown,
  };
}
