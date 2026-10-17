"use client";

import Icon from "@/components/Icon";

interface AddressListProps {
  /** Adresse commune affichée une seule fois en tête (http://hôte:port). */
  base: string;
  pages: { path: string; labelKey: string }[];
  t: (key: string) => string;
  onCopy: (text: string) => void;
  copyLabel: string;
  /** Faux quand l'hôte est déjà affiché juste au-dessus (ligne « adresse IP locale »). */
  showHost?: boolean;
}

/**
 * Pages de l'application sous un hôte unique : on ne répète plus l'adresse
 * complète sur chaque ligne (illisible sur un téléphone), seulement le
 * chemin, avec un bouton pour copier l'adresse entière.
 */
export default function AddressList({ base, pages, t, onCopy, copyLabel, showHost = true }: AddressListProps) {
  return (
    <div className="settings-paths settings-paths--compact">
      {showHost && (
        <div className="settings-host-row">
          <a href={base} target="_blank" rel="noopener noreferrer" className="settings-path-link">
            {base}
          </a>
          <button type="button" className="settings-copy-btn olc-press" onClick={() => onCopy(base)} aria-label={copyLabel} title={copyLabel}>
            <Icon name="content_copy" size={16} />
          </button>
        </div>
      )}
      {pages.map((page) => {
        const url = `${base}${page.path}`;
        return (
          <div key={page.path} className="settings-page-row">
            <a href={url} target="_blank" rel="noopener noreferrer" className="settings-page-link">
              <span className="settings-path-key">{t(page.labelKey)}</span>
              <code className="settings-page-path">{page.path}</code>
            </a>
            <button type="button" className="settings-copy-btn olc-press" onClick={() => onCopy(url)} aria-label={copyLabel} title={copyLabel}>
              <Icon name="content_copy" size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
