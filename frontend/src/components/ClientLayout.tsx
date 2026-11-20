"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import UpdateProgressOverlay from "@/components/UpdateProgressOverlay";
import LayoutToasts from "@/components/layout/LayoutToasts";
import { groupOfPath } from "@/components/layout/navActive";
import { usePlugNotice, useUpdateNotice } from "@/components/layout/useLayoutNotices";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { desktopShell, mobileShell } from "@/components/layout/LayoutShells";
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

  const [drawerPath, setDrawerPath] = useState(pathname);
  if (drawerPath !== pathname) {
    setDrawerPath(pathname);
    setDrawerOpen(false);
  }

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
  const nav = { navEntries, footerLinks, pathname, activeGroup, toggleGroup, t };

  if (isMobile) return mobileShell({ ...nav, network, drawerOpen, setDrawerOpen, overlays, children });
  return desktopShell({ ...nav, overlays, children });
}
