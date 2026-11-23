import { isNavGroup, type NavEntry, type NavLinkConfig } from "../../lib/navLinks.ts";

export function isNavLinkActive(pathname: string, href: string): boolean {
  return pathname === href || pathname === `${href}/` || pathname.startsWith(`${href}/`);
}

export function activeChildHref(children: NavLinkConfig[], pathname: string): string | null {
  const matching = children.filter((child) => isNavLinkActive(pathname, child.href));
  return matching.reduce<string | null>((best, child) => (best === null || child.href.length > best.length ? child.href : best), null);
}

export function isEntryActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : isNavLinkActive(pathname, href);
}

export type NavInfo = { iconName: string; label: string } | null;

export function activeNavInfoFor(
  navEntries: NavEntry[],
  footerLinks: Array<{ href: string; iconName: string; label: string }>,
  pathname: string,
  t: (key: string) => string,
): NavInfo {
  for (const entry of navEntries) {
    if (isNavGroup(entry)) {
      const href = activeChildHref(entry.children, pathname);
      const activeChild = entry.children.find((c) => c.href === href);
      if (activeChild) return { iconName: activeChild.iconName, label: t(activeChild.labelKey) };
    } else if (isEntryActive(pathname, entry.href)) {
      return { iconName: entry.iconName, label: t(entry.labelKey) };
    }
  }
  const activeFooter = footerLinks.find((l) => isEntryActive(pathname, l.href));
  return activeFooter ? { iconName: activeFooter.iconName, label: activeFooter.label } : null;
}

export function groupOfPath(navEntries: NavEntry[], path: string): string | null {
  for (const entry of navEntries) {
    if (isNavGroup(entry) && entry.children.some((c) => isNavLinkActive(path, c.href))) return entry.groupKey;
  }
  return null;
}
