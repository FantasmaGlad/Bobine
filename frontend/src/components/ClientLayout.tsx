"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/useIsMobile";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useAutoFullscreen } from "@/lib/useAutoFullscreen";
import { useClickSound } from "@/lib/useClickSound";
import { useScreenSafeMargin } from "@/lib/useScreenSafeMargin";
import { useScreenWakeLock } from "@/lib/useScreenWakeLock";
import { isNavGroup, visibleFooterLinks, visibleNavEntries } from "@/lib/navLinks";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";
import UpdateProgressOverlay from "@/components/UpdateProgressOverlay";
import { isFullscreenPath } from "@/lib/fullscreenRoutes";
import { useDpadNavigation } from "@/lib/useDpadNavigation";
import { isPlugEvent, useStorageEvents, type StorageEvent } from "@/lib/useStorageEvents";
import { getApiUrl } from "@/lib/apiUrl";

interface ClientLayoutProps {
  children: React.ReactNode;
}

function isNavLinkActive(pathname: string, href: string): boolean {
  return pathname === href || pathname === `${href}/` || pathname.startsWith(`${href}/`);
}

const UPDATE_TOAST_MS = 8000;

type NavInfo = { iconName: string; label: string } | null;

function activeNavInfoFor(
  navEntries: ReturnType<typeof visibleNavEntries>,
  footerLinks: Array<{ href: string; iconName: string; label: string }>,
  pathname: string,
  t: (key: string) => string,
): NavInfo {
  for (const entry of navEntries) {
    if (isNavGroup(entry)) {
      const activeChild = entry.children.find((c) => isNavLinkActive(pathname, c.href));
      if (activeChild) {
        return { iconName: activeChild.iconName, label: t(activeChild.labelKey) };
      }
    } else {
      const isActive = entry.href === "/" ? pathname === "/" : isNavLinkActive(pathname, entry.href);
      if (isActive) {
        return { iconName: entry.iconName, label: t(entry.labelKey) };
      }
    }
  }
  const activeFooter = footerLinks.find((l) => (l.href === "/" ? pathname === "/" : isNavLinkActive(pathname, l.href)));
  if (activeFooter) {
    return { iconName: activeFooter.iconName, label: activeFooter.label };
  }
  return null;
}

export default function ClientLayout({ children }: ClientLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const isMobile = useIsMobile();
  const { t, network, simplifiedUi } = useAppSettings();
  const navEntries = React.useMemo(() => visibleNavEntries(simplifiedUi), [simplifiedUi]);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [updateAvailableVersion, setUpdateAvailableVersion] = useState<string | null>(null);
  const [updateDismissed, setUpdateDismissed] = useState<boolean>(false);
  useEffect(() => {
    if (!updateAvailableVersion || updateDismissed) return;
    if (pathname === "/settings" || pathname.startsWith("/settings/")) return;
    const timer = setTimeout(() => setUpdateDismissed(true), UPDATE_TOAST_MS);
    return () => clearTimeout(timer);
  }, [updateAvailableVersion, updateDismissed, pathname]);
  const [plugEvent, setPlugEvent] = useState<"added" | "removed" | "abrupt" | null>(null);
  useAutoFullscreen(isMobile);
  const isFullscreenRoute = isFullscreenPath(pathname);
  useClickSound(!isFullscreenRoute);
  useScreenWakeLock(isFullscreenRoute);
  useScreenSafeMargin(isFullscreenRoute);
  useDpadNavigation(!isFullscreenRoute || pathname === "/coach" || pathname === "/coach/");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise l'état du tiroir avec le système de routing externe (Next.js), pas un simple calcul dérivable au rendu
    setDrawerOpen(false);
  }, [pathname]);

  const updateCheckedRef = useRef(false);
  useEffect(() => {
    if (isFullscreenRoute || updateCheckedRef.current) return;
    updateCheckedRef.current = true;
    fetch(getApiUrl("/updates/check"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (d?.has_update && !d.is_downgrade) {
          setUpdateAvailableVersion(d.latest_version ?? null);
        }
      })
      .catch(() => {});
  }, [isFullscreenRoute]);

  const footerLinks = React.useMemo(
    () => visibleFooterLinks(simplifiedUi).map((link) => ({ ...link, label: t(link.labelKey) })),
    [simplifiedUi, t],
  );

  const groupOfPath = (path: string) => {
    for (const entry of navEntries) {
      if (isNavGroup(entry) && entry.children.some((c) => isNavLinkActive(path, c.href))) return entry.groupKey;
    }
    return null;
  };
  const [activeGroup, setActiveGroup] = useState<string | null>(() => groupOfPath(pathname));
  const [groupPath, setGroupPath] = useState(pathname);
  if (groupPath !== pathname) {
    setGroupPath(pathname);
    const group = groupOfPath(pathname);
    if (group) setActiveGroup(group);
  }

  const toggleGroup = (key: string) => {
    setActiveGroup((curr) => (curr === key ? null : key));
  };

  const activeNavInfo = activeNavInfoFor(navEntries, footerLinks, pathname, t);

  const renderNavEntries = (onNavigate?: () => void) =>
    navEntries.map((entry, i) => {
      if (isNavGroup(entry)) {
        const groupActive = entry.children.some((c) => isNavLinkActive(pathname, c.href));
        const open = activeGroup === entry.groupKey;
        const groupLabel = t(entry.groupKey);
        return (
          <div key={entry.groupKey}>
            <button
              type="button"
              className={`nav-link olc-press ${groupActive ? "group-active" : ""}`}
              onClick={() => toggleGroup(entry.groupKey)}
              aria-expanded={open}
              title={groupLabel}
            >
              <Icon name={entry.iconName} size={20} weight={500} />
              <span style={{ flex: 1, textAlign: "left" }}>{groupLabel}</span>
              <Icon name={open ? "expand_more" : "chevron_right"} size={18} className="nav-group-chevron" />
            </button>
            {open && (
              <div className="nav-group-children">
                {entry.children.map((child) => {
                  const isActive = isNavLinkActive(pathname, child.href);
                  const childLabel = t(child.labelKey);
                  return (
                    <Link
                      key={child.href}
                      href={child.href}
                      onClick={onNavigate}
                      className={`nav-link olc-press ${isActive ? "active" : ""}`}
                      title={childLabel}
                    >
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
      const isActive = entry.href === "/" ? pathname === "/" : isNavLinkActive(pathname, entry.href);
      const entryLabel = t(entry.labelKey);
      return (
        <Link
          key={entry.href}
          href={entry.href}
          onClick={onNavigate}
          className={`nav-link olc-press olc-anim-in ${isActive ? "active" : ""}`}
          style={{ animationDelay: `${i * 30}ms` }}
          title={entryLabel}
        >
          <Icon name={entry.iconName} size={20} weight={500} />
          <span>{entryLabel}</span>
        </Link>
      );
    });

  const onStorageEvent = React.useCallback((event: StorageEvent) => {
    if (!isPlugEvent(event)) return;
    setPlugEvent(event.changes.includes("removed_abruptly") ? "abrupt" : event.changes.includes("removed") ? "removed" : "added");
  }, []);
  useStorageEvents(onStorageEvent, !isFullscreenRoute && !pathname.startsWith("/storage"));
  useEffect(() => {
    if (!plugEvent) return;
    const timer = setTimeout(() => setPlugEvent(null), 7000);
    return () => clearTimeout(timer);
  }, [plugEvent]);

  const renderPlugToast = () => {
    if (!plugEvent || pathname.startsWith("/storage")) return null;
    const message = plugEvent === "added" ? t("storage.pluggedBare") : plugEvent === "abrupt" ? t("storage.abruptBare") : t("storage.unpluggedBare");
    return (
      <div
        className={`toast ${plugEvent === "abrupt" ? "error" : "warning"} clickable olc-press olc-anim-in`}
        style={{ cursor: "pointer", zIndex: 1000, bottom: updateAvailableVersion && !updateDismissed ? 96 : undefined }}
        onClick={() => { setPlugEvent(null); router.push("/storage"); }}
        role="button"
        tabIndex={0}
        title={t("storage.goTo")}
      >
        <Icon name="usb" size={18} />
        <span>{message}</span>
      </div>
    );
  };

  const renderUpdateToast = () => {
    if (!updateAvailableVersion || updateDismissed || pathname === "/settings" || pathname.startsWith("/settings/")) {
      return null;
    }
    return (
      <div
        className="toast warning clickable olc-press olc-anim-in"
        style={{ cursor: "pointer", zIndex: 1000 }}
        onClick={() => router.push("/settings#updates-section")}
        role="button"
        tabIndex={0}
      >
        <Icon name="system_update" size={18} color="var(--accent-text)" />
        <span>{t("settingsPage.updateAvailable")} ({updateAvailableVersion})</span>
        <button
          type="button"
          style={{
            background: "none",
            border: "none",
            color: "inherit",
            cursor: "pointer",
            padding: "0 0 0 6px",
            display: "flex",
            alignItems: "center",
          }}
          onClick={(e) => {
            e.stopPropagation();
            setUpdateDismissed(true);
          }}
          aria-label={t("common.close")}
        >
          <Icon name="close" size={16} />
        </button>
      </div>
    );
  };

  if (isFullscreenRoute) {
    return <>{children}</>;
  }

  if (isMobile) {
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
            <div className="mobile-drawer-overlay" onClick={() => setDrawerOpen(false)} />
            <div className="mobile-drawer">
              <div className="sidebar-brand">
                <AppLogo size={72} className="brand-logo" />
              </div>
              <nav className="mobile-drawer-nav">
                {renderNavEntries(() => setDrawerOpen(false))}
                {footerLinks.map((link) => {
                  const isActive = link.href === "/" ? pathname === "/" : isNavLinkActive(pathname, link.href);
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={() => setDrawerOpen(false)}
                      className={`nav-link olc-press ${isActive ? "active" : ""}`}
                      title={link.label}
                    >
                      <Icon name={link.iconName} size={20} />
                      <span>{link.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>
          </>
        )}
        {renderUpdateToast()}
        {renderPlugToast()}
        <UpdateProgressOverlay />
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
            {renderNavEntries()}
          </nav>
        </div>

        <div className="sidebar-footer">
          {footerLinks.map((link, i) => {
            const isActive = link.href === "/" ? pathname === "/" : isNavLinkActive(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`nav-link olc-press olc-anim-in ${isActive ? "active" : ""}`}
                style={{ animationDelay: `${(navEntries.length + i) * 30}ms` }}
                title={link.label}
              >
                <Icon name={link.iconName} size={20} />
                <span>{link.label}</span>
              </Link>
            );
          })}
        </div>
      </aside>

      <div className="app-main">
        <main className="page-content">{children}</main>
      </div>
      {renderUpdateToast()}
      {renderPlugToast()}
      <UpdateProgressOverlay />
    </div>
  );
}
