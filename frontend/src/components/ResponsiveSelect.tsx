"use client";

import React, { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Highlight from "@/components/Highlight";
import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { rankByQuery } from "@/lib/searchText";
import { useIsMobile } from "@/lib/useIsMobile";

export interface SelectOption {
  value: string;
  label: string;
  /** Ligne secondaire (programme, artiste, nombre de cours...). */
  sublabel?: string;
  /** Aperçu affiché à gauche de l'élément (miniature de cours, pochette…). */
  thumbnail?: string | null;
  /** Aperçu carré (pochette d'album) plutôt que 16:9 (miniature de cours). */
  square?: boolean;
  /** Mention à droite (durée, release). */
  meta?: string;
  group?: string;
}

interface ResponsiveSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  /** Texte de l'entrée vide ; absent = pas d'entrée vide. */
  placeholder?: string;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
  disabled?: boolean;
  /** Champ de recherche intégré (par défaut au-delà de 4 éléments). */
  searchable?: boolean;
}

/** Hauteur maximale (px) de la liste déroulante sur ordinateur. */
const POPOVER_MAX_HEIGHT = 380;
const POPOVER_MIN_WIDTH = 340;

function searchTextOf(option: SelectOption): string {
  return `${option.label} ${option.sublabel ?? ""} ${option.group ?? ""} ${option.meta ?? ""}`;
}

/** Aperçu + libellés d'une option : partagé par le déclencheur, la liste déroulante et la feuille mobile. */
function OptionBody({ option, query = "" }: { option: SelectOption; query?: string }) {
  return (
    <>
      {option.thumbnail ? (
        // eslint-disable-next-line @next/next/no-img-element -- aperçu servi par l'API locale, export statique
        <img
          className={`sheet-option__thumb${option.square ? " is-square" : ""}`}
          src={option.thumbnail}
          alt=""
          loading="lazy"
        />
      ) : null}
      <span className="sheet-option__text">
        <span className="sheet-option__label">
          <Highlight text={option.label} query={query} />
        </span>
        {option.sublabel ? (
          <span className="sheet-option__sub">
            <Highlight text={option.sublabel} query={query} />
          </span>
        ) : null}
      </span>
      {option.meta ? <span className="sheet-option__meta">{option.meta}</span> : null}
    </>
  );
}

function groupOptions(options: SelectOption[]): [string, SelectOption[]][] {
  const map = new Map<string, SelectOption[]>();
  for (const option of options) {
    const key = option.group ?? "";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(option);
  }
  return [...map.entries()];
}

/**
 * Liste déroulante riche, la MÊME sur ordinateur et sur téléphone : aperçu (miniature ou pochette),
 * titre, détail et durée de chaque élément, champ de recherche intégré avec autocomplétion (accents et
 * casse ignorés, saisie surlignée) et navigation au clavier (flèches, Entrée, Échap).
 *
 * Ordinateur : liste flottante ancrée au déclencheur (portail, hors des conteneurs qui rogneraient).
 * Téléphone : feuille basse (la liste native d'Android masque l'élément choisi et n'offre aucune
 * recherche).
 */
export default function ResponsiveSelect({
  value,
  onChange,
  options,
  placeholder,
  title,
  className = "filter-select",
  style,
  disabled,
  searchable,
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
  const [anchor, setAnchor] = useState<{ left: number; top: number; width: number; above: boolean } | null>(null);

  const selected = options.find((option) => option.value === value);
  const showSearch = searchable ?? options.length > 4;
  const hasEmptyEntry = placeholder !== undefined && !query;

  const visible = useMemo(() => rankByQuery(options, query, searchTextOf), [options, query]);
  // Lignes navigables, dans l'ordre d'affichage : l'entrée vide d'abord, puis les groupes.
  const flat = useMemo(() => {
    const rows: SelectOption[] = [];
    if (hasEmptyEntry) rows.push({ value: "", label: placeholder ?? "" });
    for (const [, items] of groupOptions(visible)) rows.push(...items);
    return rows;
  }, [visible, hasEmptyEntry, placeholder]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);

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

  // Position de la liste flottante : sous le déclencheur, ou au-dessus s'il manque de place en bas.
  const measure = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const above = spaceBelow < Math.min(POPOVER_MAX_HEIGHT, 260) && rect.top > spaceBelow;
    const width = Math.max(rect.width, POPOVER_MIN_WIDTH);
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
    setAnchor({ left, top: above ? rect.top - 4 : rect.bottom + 4, width, above });
  }, []);

  useLayoutEffect(() => {
    if (!open || isMobile) return;
    measure();
    const onChangeViewport = () => measure();
    window.addEventListener("resize", onChangeViewport);
    window.addEventListener("scroll", onChangeViewport, true);
    return () => {
      window.removeEventListener("resize", onChangeViewport);
      window.removeEventListener("scroll", onChangeViewport, true);
    };
  }, [open, isMobile, measure]);

  // Fermeture au clic en dehors (déclencheur et liste exclus).
  useEffect(() => {
    if (!open || isMobile) return;
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (popoverRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      close();
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open, isMobile, close]);

  // Sans champ de recherche, la liste reçoit le focus pour que le clavier la pilote.
  useEffect(() => {
    if (open && anchor && !showSearch && !isMobile) listRef.current?.focus();
  }, [open, anchor, showSearch, isMobile]);

  // L'élément actif reste visible pendant la navigation au clavier.
  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelector<HTMLElement>(`[data-row="${activeIndex}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, activeIndex]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => Math.min(flat.length - 1, current + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(0, current - 1));
    } else if (event.key === "Home") {
      event.preventDefault();
      setActiveIndex(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActiveIndex(Math.max(0, flat.length - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const row = flat[activeIndex];
      if (row) choose(row.value);
    } else if (event.key === "Escape") {
      event.preventDefault();
      close();
      triggerRef.current?.focus();
    } else if (event.key === "Tab") {
      close();
    }
  };

  const noResults = visible.length === 0;

  // Lignes (entrée vide + groupes), identiques sur ordinateur et téléphone.
  let rowCounter = hasEmptyEntry ? 1 : 0;
  const rows = (
    <>
      {hasEmptyEntry && (
        <button
          type="button"
          role="option"
          aria-selected={value === ""}
          data-row={0}
          id={`${listId}-0`}
          className={`sheet-option olc-press${value === "" ? " is-selected" : ""}${activeIndex === 0 ? " is-active" : ""}`}
          onMouseEnter={() => setActiveIndex(0)}
          onClick={() => choose("")}
        >
          <span className="sheet-option__text">
            <span className="sheet-option__label is-placeholder">{placeholder}</span>
          </span>
          {value === "" && <Icon name="check" size={18} />}
        </button>
      )}
      {noResults ? (
        <p className="live-empty">{t("mobileRemote.noResults")}</p>
      ) : (
        groupOptions(visible).map(([group, items]) => (
          <div key={group} className="sheet-group">
            {group ? <div className="sheet-group__title">{group}</div> : null}
            {items.map((option) => {
              const index = rowCounter++;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="option"
                  aria-selected={option.value === value}
                  data-row={index}
                  id={`${listId}-${index}`}
                  className={`sheet-option olc-press${option.value === value ? " is-selected" : ""}${activeIndex === index ? " is-active" : ""}`}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => choose(option.value)}
                >
                  <OptionBody option={option} query={query} />
                  {option.value === value && <Icon name="check" size={18} />}
                </button>
              );
            })}
          </div>
        ))
      )}
    </>
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
          // Liste ouverte alors que le focus est encore sur le déclencheur : il pilote la liste.
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
        <Sheet
          open={open}
          onClose={close}
          title={title ?? placeholder}
          tall={options.length > 6}
          closeLabel={t("mobileRemote.close")}
          header={searchField ?? undefined}
        >
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
      {open &&
        anchor &&
        typeof document !== "undefined" &&
        createPortal(
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
