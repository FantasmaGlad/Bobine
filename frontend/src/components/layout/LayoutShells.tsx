"use client";

import React from "react";
import Link from "next/link";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import NavEntries from "@/components/layout/NavEntries";
import PageTransition from "@/components/layout/PageTransition";
import { activeNavInfoFor, isEntryActive } from "@/components/layout/navActive";
import { type useAppSettings } from "@/lib/AppSettingsContext";
import { type visibleNavEntries } from "@/lib/navLinks";
import { entryDelayMs } from "@/lib/entryDelay";

type FooterEntry = { href: string; iconName: string; label: string; labelKey: string };

interface NavProps {
  navEntries: ReturnType<typeof visibleNavEntries>;
  footerLinks: FooterEntry[];
  pathname: string;
  activeGroup: string | null;
  toggleGroup: (key: string) => void;
  t: ReturnType<typeof useAppSettings>["t"];
  overlays: React.ReactNode;
  children: React.ReactNode;
}

interface FooterLinkProps {
  link: { href: string; iconName: string; label: string };
  pathname: string;
  onNavigate?: () => void;
  entryIndex?: number;
}

function FooterLink({ link, pathname, onNavigate, entryIndex }: FooterLinkProps) {
  const active = isEntryActive(pathname, link.href);
  const animated = entryIndex !== undefined;
  return (
    <Link
      href={link.href}
      onClick={onNavigate}
      className={`nav-link olc-press${animated ? " olc-anim-in" : ""} ${active ? "active" : ""}`}
      style={animated ? { animationDelay: `${entryDelayMs(entryIndex)}ms` } : undefined}
      title={link.label}
    >
      <Icon name={link.iconName} size={20} />
      <span>{link.label}</span>
    </Link>
  );
}

interface MobileProps extends NavProps {
  network: ReturnType<typeof useAppSettings>["network"];
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
}

export function mobileShell({ navEntries, footerLinks, pathname, activeGroup, toggleGroup, t, overlays, children, network, drawerOpen, setDrawerOpen }: MobileProps) {
  const activeNavInfo = activeNavInfoFor(navEntries, footerLinks, pathname, t);
  const closeDrawer = () => setDrawerOpen(false);
  return (
    <div className="mobile-app-container">
      <header className="mobile-topbar">
        <button className="mobile-burger-btn olc-press" onClick={() => setDrawerOpen(true)} aria-label={t("nav.openMenu")}>
          <Icon name="menu" size={24} />
        </button>
        <div className="mobile-topbar-center">
          {activeNavInfo && (
            <>
              <Icon name={activeNavInfo.iconName} size={18} color="var(--accent-text)" />
              <span className="mobile-topbar-title">{activeNavInfo.label}</span>
            </>
          )}
        </div>
        <span className="mobile-topbar-address" title={network.localIp ? `http://${network.localIp}:${network.port}/` : network.mdnsUrl}>
          {network.localIp ? `${network.localIp}:${network.port}` : network.mdnsUrl.replace(/^https?:\/\//, "")}
        </span>
      </header>

      <main className="mobile-page-content"><PageTransition pathname={pathname}>{children}</PageTransition></main>

      {drawerOpen && (
        <>
          <div className="mobile-drawer-overlay" onClick={closeDrawer} />
          <div className="mobile-drawer">
            <div className="sidebar-brand">
              <AppLogo size={72} className="brand-logo" />
            </div>
            <nav className="mobile-drawer-nav">
              <NavEntries entries={navEntries} pathname={pathname} activeGroup={activeGroup} onToggleGroup={toggleGroup} onNavigate={closeDrawer} />
              {footerLinks.map((link) => <FooterLink key={link.href} link={link} pathname={pathname} onNavigate={closeDrawer} />)}
            </nav>
          </div>
        </>
      )}
      {overlays}
    </div>
  );
}

export function desktopShell({ navEntries, footerLinks, pathname, activeGroup, toggleGroup, overlays, children }: NavProps) {
  return (
    <div className="app-container">
      <aside className="app-sidebar">
        <div>
          <div className="sidebar-brand">
            <AppLogo size={72} className="brand-logo" />
          </div>
          <nav className="sidebar-nav">
            <NavEntries entries={navEntries} pathname={pathname} activeGroup={activeGroup} onToggleGroup={toggleGroup} />
          </nav>
        </div>
        <div className="sidebar-footer">
          {footerLinks.map((link, i) => <FooterLink key={link.href} link={link} pathname={pathname} entryIndex={navEntries.length + i} />)}
        </div>
      </aside>

      <div className="app-main">
        <main className="page-content"><PageTransition pathname={pathname}>{children}</PageTransition></main>
      </div>
      {overlays}
    </div>
  );
}
