"use client";

import React from "react";
import Link from "next/link";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { isNavGroup, type NavEntry, type NavGroupConfig } from "@/lib/navLinks";
import { isEntryActive, isNavLinkActive } from "./navActive";
import { entryDelayMs } from "@/lib/entryDelay";


interface NavEntriesProps {
  entries: NavEntry[];
  pathname: string;
  activeGroup: string | null;
  onToggleGroup: (key: string) => void;
  onNavigate?: () => void;
}

function NavGroup({ entry, pathname, open, onToggle, onNavigate }: { entry: NavGroupConfig; pathname: string; open: boolean; onToggle: () => void; onNavigate?: () => void }) {
  const { t } = useAppSettings();
  const groupActive = entry.children.some((c) => isNavLinkActive(pathname, c.href));
  const groupLabel = t(entry.groupKey);
  return (
    <div>
      <button type="button" className={`nav-link olc-press ${groupActive ? "group-active" : ""}`} onClick={onToggle} aria-expanded={open} title={groupLabel}>
        <Icon name={entry.iconName} size={20} weight={500} />
        <span style={{ flex: 1, textAlign: "left" }}>{groupLabel}</span>
        <Icon name={open ? "expand_more" : "chevron_right"} size={18} className="nav-group-chevron" />
      </button>
      {open && (
        <div className="nav-group-children">
          {entry.children.map((child) => {
            const childLabel = t(child.labelKey);
            return (
              <Link key={child.href} href={child.href} onClick={onNavigate} className={`nav-link olc-press ${isNavLinkActive(pathname, child.href) ? "active" : ""}`} title={childLabel}>
                <Icon name={child.iconName} size={20} weight={500} />
                <span>{childLabel}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function NavEntries({ entries, pathname, activeGroup, onToggleGroup, onNavigate }: NavEntriesProps) {
  const { t } = useAppSettings();
  return (
    <>
      {entries.map((entry, i) => {
        if (isNavGroup(entry)) {
          return (
            <NavGroup key={entry.groupKey} entry={entry} pathname={pathname} open={activeGroup === entry.groupKey}
              onToggle={() => onToggleGroup(entry.groupKey)} onNavigate={onNavigate} />
          );
        }
        const entryLabel = t(entry.labelKey);
        return (
          <Link
            key={entry.href}
            href={entry.href}
            onClick={onNavigate}
            className={`nav-link olc-press olc-anim-in ${isEntryActive(pathname, entry.href) ? "active" : ""}`}
            style={{ animationDelay: `${entryDelayMs(i)}ms` }}
            title={entryLabel}
          >
            <Icon name={entry.iconName} size={20} weight={500} />
            <span>{entryLabel}</span>
          </Link>
        );
      })}
    </>
  );
}
