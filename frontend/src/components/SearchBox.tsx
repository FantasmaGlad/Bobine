"use client";

import React, { useId, useMemo, useState } from "react";
import Highlight from "@/components/Highlight";
import { suggestFrom } from "@/lib/searchText";

interface SearchBoxProps {
  value: string;
  onChange: (value: string) => void;
  /** Textes dont tirer les suggestions d'autocomplétion (titres, artistes, catégories…). Absent = champ simple. */
  suggestions?: readonly string[];
  placeholder?: string;
  ariaLabel?: string;
  className?: string;
  style?: React.CSSProperties;
  autoFocus?: boolean;
  /** Validation au clavier (Entrée) quand aucune suggestion n'est surlignée. */
  onSubmit?: (value: string) => void;
  /** Nombre maximal de suggestions affichées. */
  limit?: number;
}

/**
 * Champ de recherche avec autocomplétion : au fil de la frappe, propose les textes les plus pertinents
 * (début de texte, puis début de mot — accents et casse ignorés, cf. lib/searchText.ts) avec la saisie
 * surlignée. Flèches haut/bas pour naviguer, Entrée ou clic pour choisir, Échap pour refermer.
 * Combobox ARIA : lisible au lecteur d'écran et à la télécommande.
 */
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
  const [active, setActive] = useState(-1);
  // Liste refermée par Échap ou après un choix, jusqu'à la prochaine frappe.
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);

  const list = useMemo(() => (suggestions ? suggestFrom(suggestions, value, limit) : []), [suggestions, value, limit]);
  const open = focused && list.length > 0 && dismissedFor !== value;
  const activeIndex = active >= 0 && active < list.length ? active : -1;

  const pick = (text: string) => {
    onChange(text);
    setDismissedFor(text);
    setActive(-1);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" && list.length > 0) {
      event.preventDefault();
      setDismissedFor(null);
      setActive((current) => (current + 1) % list.length);
    } else if (event.key === "ArrowUp" && list.length > 0) {
      event.preventDefault();
      setDismissedFor(null);
      setActive((current) => (current <= 0 ? list.length - 1 : current - 1));
    } else if (event.key === "Enter") {
      if (open && activeIndex >= 0) {
        event.preventDefault();
        pick(list[activeIndex]);
      } else {
        onSubmit?.(value);
      }
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      setDismissedFor(value);
      setActive(-1);
    }
  };

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
          setDismissedFor(null);
          setActive(-1);
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
              // mousedown (et non click) : le champ perdrait le focus avant le clic et la liste se fermerait.
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
