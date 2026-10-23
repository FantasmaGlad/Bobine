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
import { navEntries, isNavGroup, footerNavLinks as footerNavLinkConfigs } from "@/lib/navLinks";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";
import UpdateProgressOverlay from "@/components/UpdateProgressOverlay";
import { isFullscreenPath } from "@/lib/fullscreenRoutes";
import { useDpadNavigation } from "@/lib/useDpadNavigation";
import { isPlugEvent, useStorageEvents, type StorageEvent } from "@/lib/useStorageEvents";

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

interface ClientLayoutProps {
  children: React.ReactNode;
}

/**
 * Un lien de nav est actif sur sa propre page ET ses sous-pages, mais pas sur
 * une AUTRE page dont le chemin partage juste le même préfixe textuel (bug
 * "Playlists audio sélectionne aussi Cours audio" : "/audio-playlists/"
 * commence bien par "/audio" en tant que chaîne, sans être une sous-page de
 * "/audio/"). On exige donc une frontière de segment (`/`) après le préfixe.
 */
function isNavLinkActive(pathname: string, href: string): boolean {
  return pathname === href || pathname === `${href}/` || pathname.startsWith(`${href}/`);
}

export default function ClientLayout({ children }: ClientLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const isMobile = useIsMobile();
  const { t, network } = useAppSettings();
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [updateAvailableVersion, setUpdateAvailableVersion] = useState<string | null>(null);
  const [updateDismissed, setUpdateDismissed] = useState<boolean>(false);
  // Branchement ou retrait d'un support externe, où que l'on soit dans l'administration (sans nom : l'évènement n'en porte pas).
  const [plugEvent, setPlugEvent] = useState<"added" | "removed" | "abrupt" | null>(null);
  // demande le
  // plein écran navigateur dès le premier tap (le remote/coach mobile n'a
  // aucune raison de garder la barre d'adresse visible).
  useAutoFullscreen(isMobile);
  // Son de clic : uniquement dans le studio admin, pas
  // sur l'écran cinéma/kiosk ni le mode coach (appels de hooks toujours
  // inconditionnels, seul `enabled` varie selon la route).
  // Comparaison sur le pathname EXACT (lib/fullscreenRoutes.ts) : /radio est un poste de
  // diffusion, /radio-library et /radio-remote restent des pages d'admin normales.
  const isFullscreenRoute = isFullscreenPath(pathname);
  useClickSound(!isFullscreenRoute);
  // Anti-veille automatique (Screen Wake Lock API) sur les écrans de diffusion
  // et d'attente.
  useScreenWakeLock(isFullscreenRoute);
  // Marge de sécurité (overscan TV) propre à cet écran, réglée par ?safe=<0-10>.
  useScreenSafeMargin(isFullscreenRoute);
  // Navigation à la télécommande dans toute l'administration et dans le coach. /cinema, /grid, /kiosk et
  // /radio gèrent déjà leurs propres touches (useKioskRemote) et ne l'activent pas.
  useDpadNavigation(!isFullscreenRoute || pathname === "/coach" || pathname === "/coach/");

  // La navigation ferme le tiroir mobile automatiquement.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise l'état du tiroir avec le système de routing externe (Next.js), pas un simple calcul dérivable au rendu
    setDrawerOpen(false);
  }, [pathname]);

  // Notification de mise à jour globale cliquable — vérifiée UNE SEULE FOIS
  // par chargement de page (`updateCheckedRef`), pas à chaque bascule entre
  // une route plein écran et une route normale : ce composant reste monté
  // en permanence, et `isFullscreenRoute` en dépendance seule refaisait un
  // appel réseau (et pouvait rouvrir la bannière après une fermeture
  // manuelle) à chaque aller-retour /cinema|/kiosk|/coach|/grid|/radio <->
  // reste de l'admin — cause racine confirmée du constat "la notification
  // apparaît en continu". La dépendance sur `isFullscreenRoute` est
  // conservée pour permettre la toute première vérification une fois
  // sortie d'une route plein écran, quand la page a été chargée
  // directement dessus.
  const updateCheckedRef = useRef(false);
  useEffect(() => {
    if (isFullscreenRoute || updateCheckedRef.current) return;
    updateCheckedRef.current = true;
    fetch(getApiUrl("/updates/check"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        // Un retour en arrière Bêta -> Stable est un choix explicite de
        // l'utilisateur (sélecteur de canal), jamais une "nouveauté" à
        // annoncer sur chaque page.
        if (d?.has_update && !d.is_downgrade) {
          setUpdateAvailableVersion(d.latest_version ?? null);
        }
      })
      .catch(() => {});
  }, [isFullscreenRoute]);

  // icônes Google Material Symbols reprises telles
  // quelles du design importé (surface "PC Admin") plutôt que les SVG
  // Heroicons d'origine, pour une identité visuelle cohérente avec le reste
  // de la refonte.
  const footerLinks = footerNavLinkConfigs.map((link) => ({ ...link, label: t(link.labelKey) }));

  // Regroupements dépliables (accordéon exclusif) :
  // Lors de la navigation ou d'un clic d'accordéon, fermer les autres
  // groupes pour garder l'arborescence fermée, lisible et propre.
  const [activeGroup, setActiveGroup] = useState<string | null>(() => {
    for (const entry of navEntries) {
      if (isNavGroup(entry) && entry.children.some((c) => isNavLinkActive(pathname, c.href))) {
        return entry.groupKey;
      }
    }
    return null;
  });

  useEffect(() => {
    for (const entry of navEntries) {
      if (isNavGroup(entry) && entry.children.some((c) => isNavLinkActive(pathname, c.href))) {
        setActiveGroup(entry.groupKey);
        return;
      }
    }
  }, [pathname]);

  const toggleGroup = (key: string) => {
    setActiveGroup((curr) => (curr === key ? null : key));
  };

  const activeNavInfo = React.useMemo(() => {
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
  }, [pathname, t, footerLinks]);

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
        <Icon name="system_update" size={18} color="var(--accent-primary)" />
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
          aria-label="Fermer"
        >
          <Icon name="close" size={16} />
        </button>
      </div>
    );
  };

  // L'écran kiosk, l'interface cinéma adhérents et le mode coach mobile
  // n'ont ni sidebar ni en-tête d'administration : plein écran dédié
  // uniquement.
  if (isFullscreenRoute) {
    return <>{children}</>;
  }

  if (isMobile) {
    // Pas de navigation permanente visible sur mobile — l'écran
    // principal (la page courante, généralement la télécommande) occupe tout
    // l'espace, la navigation reste dans un tiroir discret (burger).
    return (
      <div className="mobile-app-container">
        <header className="mobile-topbar">
          <button className="mobile-burger-btn olc-press" onClick={() => setDrawerOpen(true)} aria-label={t("nav.openMenu")}>
            <Icon name="menu" size={24} />
          </button>
          <div className="mobile-topbar-center">
            {activeNavInfo && (
              <>
                <Icon name={activeNavInfo.iconName} size={18} color="var(--accent-primary)" />
                <span className="mobile-topbar-title">{activeNavInfo.label}</span>
              </>
            )}
          </div>
          {/* IP/URL de CETTE terminaison plutôt que le logo (trop petit pour
              être utile ici) : un visiteur dépanné sur plusieurs terminaisons
              (câblé, réseau, kiosque) doit pouvoir identifier d'un coup
              d'œil celle qu'il a sous les yeux. Source : `network.localIp`
              (IP LAN réelle, déjà exposée par le backend pour la découverte
              réseau), jamais `window.location` — un accès via `bobine.local`
              ou `localhost` en dev afficherait une valeur non pertinente. */}
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
      {/* Sidebar */}
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

      {/* Main Area */}
      <div className="app-main">
        {/* En-tête retiré : le contenu occupe tout l'espace ;
            le statut système (Watcher/Écran) est déplacé dans Paramètres. */}
        <main className="page-content">{children}</main>
      </div>
      {renderUpdateToast()}
      {renderPlugToast()}
      <UpdateProgressOverlay />
    </div>
  );
}
