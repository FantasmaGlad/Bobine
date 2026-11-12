"use client";

import Icon from "@/components/Icon";

interface AddressListProps {
  base: string;
  pages: { path: string; labelKey: string }[];
  t: (key: string) => string;
  onCopy: (text: string) => void;
  copyLabel: string;
  showHost?: boolean;
}

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
