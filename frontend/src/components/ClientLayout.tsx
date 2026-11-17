"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import UpdateProgressOverlay from "@/components/UpdateProgressOverlay";
import LayoutToasts from "@/components/layout/LayoutToasts";
import NavEntries from "@/components/layout/NavEntries";
import { activeNavInfoFor, groupOfPath, isEntryActive } from "@/components/layout/navActive";
import { usePlugNotice, useUpdateNotice } from "@/components/layout/useLayoutNotices";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { isFullscreenPath } from "@/lib/fullscreenRoutes";
import { visibleFooterLinks, visibleNavEntries } from "@/lib/navLinks";
import { useAutoFullscreen } from "@/lib/useAutoFullscreen";
import { useClickSound } from "@/lib/useClickSound";
import { useDpadNavigation } from "@/lib/useDpadNavigation";
import { useIsMobile } from "@/lib/useIsMobile";
import { useScreenSafeMargin } from "@/lib/useScreenSafeMargin";
import { useScreenWakeLock } from "@/lib/useScreenWakeLock";

interface ClientLayoutProps {
  children: React.ReactNode;
}

function useScreenBehaviour(pathname: string, isMobile: boolean, isFullscreenRoute: boolean) {
  useAutoFullscreen(isMobile);
  useClickSound(!isFullscreenRoute);
  useScreenWakeLock(isFullscreenRoute);
  useScreenSafeMargin(isFullscreenRoute);
  useDpadNavigation(!isFullscreenRoute || pathname === "/coach" || pathname === "/coach/");
}

function useActiveGroup(entries: ReturnType<typeof visibleNavEntries>, pathname: string) {
  const [activeGroup, setActiveGroup] = useState<string | null>(() => groupOfPath(entries, pathname));
  const [groupPath, setGroupPath] = useState(pathname);
  if (groupPath !== pathname) {
    setGroupPath(pathname);
    const group = groupOfPath(entries, pathname);
    if (group) setActiveGroup(group);
  }
  const toggleGroup = (key: string) => setActiveGroup((curr) => (curr === key ? null : key));
  return { activeGroup, toggleGroup };
}

interface FooterLinkProps {
  link: { href: string; iconName: string; label: string };
  pathname: string;
  onNavigate?: () => void;
  animationDelay?: number;
}

function FooterLink({ link, pathname, onNavigate, animationDelay }: FooterLinkProps) {
  const active = isEntryActive(pathname, link.href);
  const animated = animationDelay !== undefined;
  return (
    <Link
      href={link.href}
      onClick={onNavigate}
      className={`nav-link olc-press${animated ? " olc-anim-in" : ""} ${active ? "active" : ""}`}
      style={animated ? { animationDelay: `${animationDelay}ms` } : undefined}
      title={link.label}
    >
      <Icon name={link.iconName} size={20} />
      <span>{link.label}</span>
    </Link>
  );
}

export default function ClientLayout({ children }: ClientLayoutProps) {
  const pathname = usePathname();
  const isMobile = useIsMobile();
  const { t, network, simplifiedUi } = useAppSettings();
  const navEntries = React.useMemo(() => visibleNavEntries(simplifiedUi), [simplifiedUi]);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const isFullscreenRoute = isFullscreenPath(pathname);
  useScreenBehaviour(pathname, isMobile, isFullscreenRoute);
  const update = useUpdateNotice(pathname, isFullscreenRoute);
  const plug = usePlugNotice(!isFullscreenRoute && !pathname.startsWith("/storage"));
  const { activeGroup, toggleGroup } = useActiveGroup(navEntries, pathname);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise l'état du tiroir avec le système de routing externe (Next.js), pas un simple calcul dérivable au rendu
    setDrawerOpen(false);
  }, [pathname]);

  const footerLinks = React.useMemo(
    () => visibleFooterLinks(simplifiedUi).map((link) => ({ ...link, label: t(link.labelKey) })),
    [simplifiedUi, t],
  );

  if (isFullscreenRoute) {
    return <>{children}</>;
  }

  const overlays = (
    <>
      <LayoutToasts pathname={pathname} update={update} plug={plug} />
      <UpdateProgressOverlay />
    </>
  );

  if (isMobile) {
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

        <main className="mobile-page-content">{children}</main>

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
          {footerLinks.map((link, i) => <FooterLink key={link.href} link={link} pathname={pathname} animationDelay={(navEntries.length + i) * 30} />)}
        </div>
      </aside>

      <div className="app-main">
        <main className="page-content">{children}</main>
      </div>
      {overlays}
    </div>
  );
}
