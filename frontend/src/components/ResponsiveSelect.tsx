"use client";

import React, { useMemo, useState } from "react";
import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useIsMobile } from "@/lib/useIsMobile";

export interface SelectOption {
  value: string;
  label: string;
  /** Ligne secondaire (programme, nombre de cours...). */
  sublabel?: string;
  /** Miniature affichée dans la feuille (téléphone). */
  thumbnail?: string | null;
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
  /** Champ de recherche dans la feuille (par défaut au-delà de 7 éléments). */
  searchable?: boolean;
}

/**
 * Liste déroulante : `<select>` natif sur ordinateur, feuille basse avec
 * recherche, miniatures et sélection visible sur téléphone (la liste native
 * d'Android masque l'élément choisi et n'offre aucune recherche).
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
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const selected = options.find((option) => option.value === value);
  const showSearch = searchable ?? options.length > 7;

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((option) => `${option.label} ${option.sublabel ?? ""} ${option.group ?? ""}`.toLowerCase().includes(needle));
  }, [options, query]);

  const groups = useMemo(() => {
    const map = new Map<string, SelectOption[]>();
    for (const option of visible) {
      const key = option.group ?? "";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(option);
    }
    return [...map.entries()];
  }, [visible]);

  if (!isMobile) {
    const grouped = options.some((option) => option.group);
    const byGroup = new Map<string, SelectOption[]>();
    if (grouped) {
      for (const option of options) {
        const key = option.group ?? "";
        if (!byGroup.has(key)) byGroup.set(key, []);
        byGroup.get(key)!.push(option);
      }
    }
    return (
      <select className={className} style={style} value={value} title={title} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {grouped
          ? [...byGroup.entries()].map(([group, items]) => (
              <optgroup key={group} label={group}>
                {items.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                    {option.sublabel ? ` — ${option.sublabel}` : ""}
                  </option>
                ))}
              </optgroup>
            ))
          : options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
                {option.sublabel ? ` — ${option.sublabel}` : ""}
              </option>
            ))}
      </select>
    );
  }

  const close = () => {
    setOpen(false);
    setQuery("");
  };
  const choose = (next: string) => {
    onChange(next);
    close();
  };

  return (
    <>
      <button
        type="button"
        className={`select-trigger ${className}`}
        style={style}
        disabled={disabled}
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
      >
        <span className={`select-trigger__label${selected ? "" : " is-placeholder"}`}>{selected ? selected.label : placeholder ?? ""}</span>
        <Icon name="expand_more" size={20} />
      </button>
      <Sheet
        open={open}
        onClose={close}
        title={title ?? placeholder}
        tall={options.length > 6}
        closeLabel={t("mobileRemote.close")}
        header={
          showSearch ? (
            <input
              type="search"
              className="search-input sheet-search"
              placeholder={t("mobileRemote.searchPlaceholder")}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoComplete="off"
              enterKeyHint="search"
            />
          ) : undefined
        }
      >
        {placeholder !== undefined && !query && (
          <button type="button" className={`sheet-option olc-press${value === "" ? " is-selected" : ""}`} onClick={() => choose("")}>
            <span className="sheet-option__text">
              <span className="sheet-option__label is-placeholder">{placeholder}</span>
            </span>
            {value === "" && <Icon name="check" size={20} />}
          </button>
        )}
        {groups.length === 0 || visible.length === 0 ? (
          <p className="live-empty">{t("mobileRemote.noResults")}</p>
        ) : (
          groups.map(([group, items]) => (
            <div key={group} className="sheet-group">
              {group ? <div className="sheet-group__title">{group}</div> : null}
              {items.map((option) => (
                <button key={option.value} type="button" className={`sheet-option olc-press${option.value === value ? " is-selected" : ""}`} onClick={() => choose(option.value)}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- miniature servie par l'API locale, export statique */}
                  {option.thumbnail ? <img className="sheet-option__thumb" src={option.thumbnail} alt="" loading="lazy" /> : null}
                  <span className="sheet-option__text">
                    <span className="sheet-option__label">{option.label}</span>
                    {option.sublabel ? <span className="sheet-option__sub">{option.sublabel}</span> : null}
                  </span>
                  {option.meta ? <span className="sheet-option__meta">{option.meta}</span> : null}
                  {option.value === value && <Icon name="check" size={20} />}
                </button>
              ))}
            </div>
          ))
        )}
      </Sheet>
    </>
  );
}
