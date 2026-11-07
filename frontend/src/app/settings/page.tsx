"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import BrowserCompatibility from "@/components/BrowserCompatibility";
import MediaNativeSetting from "@/components/MediaNativeSetting";
import { useAppSettings } from "@/lib/AppSettingsContext";
import SegmentedTabs from "@/components/SegmentedTabs";
import PageNav from "@/components/PageNav";
import { DEFAULT_SETTINGS_CATEGORY, SETTINGS_CATEGORIES, categoryOfSection, matchCategories, type SettingsCategoryId } from "@/lib/settingsCategories";
import { paletteOf, THEME_MODES, THEMES, type ThemeMode } from "@/lib/themePalettes";
import { channelI18nSuffix, channelLogoUrl, isRollingReleaseChannel, RELEASE_CHANNELS, type UpdateChannel } from "@/lib/releaseChannel";
import type { Language } from "@/lib/i18n";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";
import MarkdownView from "@/components/MarkdownView";
import AddressList from "@/components/AddressList";
import StartOnBootToggle from "@/components/StartOnBootToggle";
import ImportDiagnosticsPanel from "@/components/ImportDiagnosticsPanel";
import { useIsMobile } from "@/lib/useIsMobile";
import { copyText } from "@/lib/clipboard";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { loadMode, saveMode, type GlassMode } from "@/lib/glassQuality";

// Profil de déploiement — détermine si
// la zone Désinstaller propose une action directe (appliance headless) ou de
// simples instructions (profils desktop, cf. section "Zone de danger" plus
// bas).
// "android" ajouté : absent
// depuis l'introduction du profil Android — les comparaisons
// strictes contre "android" existaient déjà ailleurs dans le dépôt
// (cinema/page.tsx) mais sur des données non typées (`any`), ce qui
// masquait le type manquant ici.
type DeploymentProfile = "linux-headless" | "linux-desktop" | "windows" | "macos" | "android";

interface SettingsData {
  /** Faux sur Android : le redémarrage n'y est pas relancé de façon garantie. */
  restart_guaranteed?: boolean;
  wait_time_between_courses: number;
  volume_default: number;
  audio_chain_timer_seconds: number;
  radio_announcement_fade_ms: number;
  logs_retention_days?: number;
  deployment_profile: DeploymentProfile;
  paths: Record<string, string>;
  network: {
    local_ip: string | null;
    port: number;
    mdns_url: string;
    mdns_status: string | null;
    /** Vrai si le port 80 renvoie réellement vers Bobine (adresse courte valable). */
    port80_redirect?: boolean;
    /** Liens d'accès complets (mêmes données que l'API) : boucle locale, réseau local, VPN, bobine.local. */
    access?: { kind: "loopback" | "lan" | "vpn" | "mdns"; interface: string; url: string }[];
  };
  update_channel: UpdateChannel;
  wired_display_mode: "dual_screen" | "headless";
  auto_update_enabled: "true" | "false";
  auto_update_time: string;
  auto_update_supported?: boolean;
  /** Faux sur l'appliance et en boutique : une partie du trafic de mise à jour ne passerait pas par Tor. */
  update_tor_supported?: boolean;
  update_tor?: "true" | "false";
  update_tor_proxy?: string;
  /** Build Google Play : les mises à jour passent par la boutique (pas de canaux GitHub ni d'installateur planifié). */
  store_managed?: boolean;
}

/** État de la mise à jour côté Google Play (build « play » uniquement). */
interface StoreInfo {
  provider: "google_play";
  state: "none" | "available" | "downloading" | "downloaded" | "installing" | "failed" | "unavailable";
  version_code?: number | null;
  message?: string;
}


interface UpdateInfo {
  online: boolean;
  channel?: UpdateChannel;
  current_version: string;
  current_tag: string;
  current_commit: string;
  latest_version: string | null;
  has_update: boolean;
  /** Vrai quand la version proposée est ANTÉRIEURE à celle installée
   * (retour Bêta/Canary -> Stable demandé explicitement via le sélecteur de canal). */
  is_downgrade?: boolean;
  error_code?: "offline" | "rate_limited" | `not_found_${UpdateChannel}` | null;
  local_build?: UpdateChannel;
  release_title: string | null;
  release_notes: string | null;
  published_at: string | null;
  html_url: string | null;
  can_auto_apply?: boolean;
  /** Application installée depuis une boutique (Google Play) : les mises à jour passent par elle. */
  store_managed?: boolean;
  store?: StoreInfo;
  download_url?: string | null;
  asset_name?: string | null;
  asset_size?: number | null;
  deployment_profile?: DeploymentProfile;
  message?: string;
  checked_at: string;
}


/** Octets -> unité lisible (Go/Mo…), base 1024. */
function formatBytes(bytes: number): string {
  if (!bytes || bytes < 0) return "0 o";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

interface ToastState {
  message: string;
  type: "success" | "error" | "warning";
  onClick?: () => void;
}

interface LidInfo {
  has_lid: boolean;
  prevent_sleep: boolean;
}

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

// Pages plein écran destinées à être ouvertes depuis un AUTRE appareil du
// réseau local (TV câblée, tablette coach, poste radio dédié…) — même liste que
// `isFullscreenRoute` dans ClientLayout.tsx.
const PUBLIC_PAGE_KEYS: { path: string; labelKey: string }[] = [
  { path: "/kiosk", labelKey: "settingsPage.paths.pageKiosk" },
  // Écran explicitement rattaché au canal RÉSEAU : seul moyen d'en avoir un
  // sur la machine du serveur (127.0.0.1), où le nom d'hôte désigne sinon le
  // canal câblé (cf. lib/displayChannel.ts).
  { path: "/kiosk?channel=network", labelKey: "settingsPage.paths.pageKioskNetwork" },
  { path: "/cinema", labelKey: "settingsPage.paths.pageCinema" },
  { path: "/coach", labelKey: "settingsPage.paths.pageCoach" },
  // Une radio par sortie de diffusion : chacune a son propre moteur (playlist, volume,
  // rappels, planning, son). `/radio` nu reste un alias historique de la sortie réseau.
  { path: "/radio?channel=cable", labelKey: "settingsPage.paths.pageRadioCable" },
  { path: "/radio?channel=network", labelKey: "settingsPage.paths.pageRadioNetwork" },
];

// /grid (écran tactile de sélection) : spécifique au profil
// Android — inutile de l'afficher sur les autres profils, qui n'ont pas
// cette page.
const ANDROID_PAGE_KEYS: { path: string; labelKey: string }[] = [
  { path: "/grid", labelKey: "settingsPage.paths.pageGrid" },
];

const PATH_LABEL_KEYS: Record<string, string> = {
  database_url: "settingsPage.paths.database_url",
  media_dir: "settingsPage.paths.media_dir",
  watch_dir: "settingsPage.paths.watch_dir",
  thumbnails_dir: "settingsPage.paths.thumbnails_dir",
  backgrounds_dir: "settingsPage.paths.backgrounds_dir",
  backgrounds_watch_dir: "settingsPage.paths.backgrounds_watch_dir",
  audio_dir: "settingsPage.paths.audio_dir",
  audio_watch_dir: "settingsPage.paths.audio_watch_dir",
  radio_dir: "settingsPage.paths.radio_dir",
  radio_watch_dir: "settingsPage.paths.radio_watch_dir",
  radio_covers_dir: "settingsPage.paths.radio_covers_dir",
  radio_announcements_dir: "settingsPage.paths.radio_announcements_dir",
  branding_dir: "settingsPage.paths.branding_dir",
  logs_dir: "settingsPage.paths.logs_dir",
  subtitles_dir: "settingsPage.paths.subtitles_dir",
};

// Phrase à recopier pour armer la désinstallation (comparée sans casse/accent).
const UNINSTALL_PHRASE = "DÉSINSTALLER";
const RESET_DATA_PHRASE = "RÉINITIALISER";
const normalizePhrase = (s: string) => s.trim().toUpperCase().replace(/É/g, "E");

export default function SettingsPage() {
  const {
    theme, themeMode, resolvedMode, language, storedLanguage, languagePending, simplifiedUi, setSimplifiedUi, setTheme, setThemeMode, setLanguage, t,
    hasCustomLogo, activeLogo, setActiveLogo, refreshBranding,
    wiredDisplayMode, displayModeSetting, setDisplayModeSetting, displayExternalCount,
  } = useAppSettings();

  // Catégories : la page n'affiche que celle choisie ; une recherche affiche toutes les catégories qui répondent.
  const [category, setCategory] = useState<SettingsCategoryId>(DEFAULT_SETTINGS_CATEGORY);
  const [query, setQuery] = useState("");
  const searching = query.trim().length > 0;
  const matched = useMemo(
    () => matchCategories(query, (id) => ["label", "desc", "keywords"].map((part) => t(`settingsPage.cat.${id}.${part}`)).join(" ")),
    [query, t],
  );
  const shows = (sectionId: string) => {
    const owner = categoryOfSection(sectionId);
    return searching ? owner !== undefined && matched.has(owner) : owner === category;
  };
  const chooseCategory = (id: SettingsCategoryId) => {
    setQuery("");
    setCategory(id);
  };
  /** Ouvre la catégorie d'une section puis la fait défiler (liens profonds, notifications). */
  const openSection = useCallback((sectionId: string) => {
    const owner = categoryOfSection(sectionId);
    if (owner) {
      setQuery("");
      setCategory(owner);
    }
    window.setTimeout(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }, []);
  useEffect(() => {
    const target = window.location.hash.replace(/^#/, "");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture de l'adresse au montage (lien profond vers une section)
    if (target && categoryOfSection(target)) openSection(target);
  }, [openSection]);
  const isMobile = useIsMobile();
  const [glassMode, setGlassMode] = useState<GlassMode>("auto");
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- relit le réglage mémorisé dans le navigateur au montage
    setGlassMode(loadMode());
  }, []);
  const [data, setData] = useState<SettingsData | null>(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);
  // Redémarrage simple : les écrans ouverts se reconnectent, voient un autre boot_id et se rechargent seuls.
  const restartNow = async () => {
    setRestarting(true);
    setRestartMessage(null);
    try {
      const res = await fetch(getApiUrl("/settings/system/restart"), { method: "POST" });
      setRestartMessage(t(res.ok ? "settingsPage.languageRestarting" : "settingsPage.languageRestartFailed"));
      if (!res.ok) setRestarting(false);
      else {
        // Sans relance observable (poste de développement), la page ne se recharge jamais : on rend la main.
        window.setTimeout(() => {
          setRestarting(false);
          setRestartMessage(t("settingsPage.languageRestartFailed"));
        }, 30000);
      }
    } catch {
      setRestartMessage(t("settingsPage.languageRestartFailed"));
      setRestarting(false);
    }
  };
  const [loading, setLoading] = useState(true);

  const [refreshingNetwork, setRefreshingNetwork] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [confirmingChannel, setConfirmingChannel] = useState<UpdateChannel | null>(null);
  const [resetting, setResetting] = useState(false);
  const [showUninstall, setShowUninstall] = useState(false);
  const [uninstallConfirm, setUninstallConfirm] = useState("");
  const [uninstalling, setUninstalling] = useState(false);

  // Sauvegarde & Restauration
  const [exportingBackup, setExportingBackup] = useState(false);
  const [restoringBackup, setRestoringBackup] = useState(false);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
  const [selectedBackupFile, setSelectedBackupFile] = useState<File | null>(null);

  // Remise à zéro des données
  const [showResetData, setShowResetData] = useState(false);
  const [resetDataConfirm, setResetDataConfirm] = useState("");
  const [resettingData, setResettingData] = useState(false);

  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [storeBusy, setStoreBusy] = useState(false);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [applyingUpdate, setApplyingUpdate] = useState(false);
  const [showReleaseNotes, setShowReleaseNotes] = useState(false);
  const [changingChannel, setChangingChannel] = useState(false);

  // Nettoyage automatique des journaux & métriques
  const [logsRetentionDays, setLogsRetentionDays] = useState<number>(7);
  const [isPurgingLogs, setIsPurgingLogs] = useState<boolean>(false);

  const [lidInfo, setLidInfo] = useState<LidInfo | null>(null);
  const [updatingLid, setUpdatingLid] = useState(false);

  const showToast = (message: string, type: ToastState["type"] = "success", onClick?: () => void) =>
    setToast({ message, type, onClick });

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    fetch(getApiUrl("/settings/laptop-lid"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((info) => {
        if (info) setLidInfo(info);
      })
      .catch(() => {});
  }, []);

  const handleToggleLid = async (preventSleep: boolean) => {
    setUpdatingLid(true);
    try {
      const res = await fetch(getApiUrl("/settings/laptop-lid"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prevent_sleep: preventSleep }),
      });
      if (res.ok) {
        const updated: LidInfo = await res.json();
        setLidInfo(updated);
        showToast(t("settingsPage.clamshellApplied"), "success");
      } else {
        showToast(t("settingsPage.clamshellError"), "error");
      }
    } catch {
      showToast(t("settingsPage.clamshellError"), "error");
    } finally {
      setUpdatingLid(false);
    }
  };

  const fetchSettings = useCallback((showIndicator = false) => {
    if (showIndicator) setRefreshingNetwork(true);
    return fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (d) {
          setData(d);
          if (typeof d.logs_retention_days === "number") {
            setLogsRetentionDays(d.logs_retention_days);
          }
        }
      })
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        if (showIndicator) setRefreshingNetwork(false);
      });
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial depuis le backend puis rafraîchissement périodique, pas un calcul dérivable au rendu
    fetchSettings();
    const id = setInterval(() => fetchSettings(false), 15000);
    return () => clearInterval(id);
  }, [fetchSettings]);




  const handleLogoUpload = async (file: File) => {
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(getApiUrl("/settings/logo"), { method: "POST", body: formData });
      if (res.ok) {
        refreshBranding();
        showToast(t("settingsPage.logoUploadSuccess"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("settingsPage.logoUploadError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleLogoReset = async () => {
    setUploadingLogo(true);
    try {
      const res = await fetch(getApiUrl("/settings/logo"), { method: "DELETE" });
      if (res.ok) {
        refreshBranding();
        showToast(t("settingsPage.logoResetSuccess"));
      } else {
        showToast(t("settingsPage.logoUploadError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleFullReset = async () => {
    setResetting(true);
    try {
      const res = await fetch(getApiUrl("/settings/system/reset"), { method: "POST" });
      if (res.ok) {
        showToast(t("settingsPage.syncResetSuccess"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("settingsPage.syncResetError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setResetting(false);
      setShowResetConfirm(false);
    }
  };

  const handleUninstall = async () => {
    setUninstalling(true);
    try {
      const res = await fetch(getApiUrl("/settings/system/uninstall"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: uninstallConfirm }),
      });
      const payload = await res.json().catch(() => ({}));
      if (res.ok) {
        showToast(payload.message || t("settingsPage.uninstallStarted"), "warning");
      } else {
        showToast(payload.detail || t("settingsPage.uninstallError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUninstalling(false);
      setShowUninstall(false);
      setUninstallConfirm("");
    }
  };

  // `silent` : la
  // vérification automatique au montage de la page ne doit pas déranger
  // l'utilisateur avec un toast "Système à jour" à chaque ouverture des
  // Réglages — seule une mise à jour RÉELLEMENT disponible mérite un toast
  // non sollicité. Le clic manuel sur "Rechercher une mise à jour" garde
  // lui son retour complet (y compris "à jour"/erreur), pour confirmer que
  // le clic a bien fait quelque chose.
  const checkForUpdates = async (silent = false) => {
    setCheckingUpdate(true);
    try {
      // `refresh=1` : un clic explicite (ou un changement de canal) doit
      // contourner la fenêtre anti-doublon du serveur ; l'ouverture
      // silencieuse de la page peut, elle, réutiliser une réponse récente.
      const res = await fetch(getApiUrl(`/updates/check${silent ? "" : "?refresh=1"}`), { cache: "no-store" });
      if (res.ok) {
        const info: UpdateInfo = await res.json();
        setUpdateInfo(info);
        if (info.store_managed) {
          // Build Google Play : l'état vient de Google Play, jamais des releases GitHub.
          const state = info.store?.state;
          if (state === "available") {
            showToast(t("settingsPage.storeAvailable"), "warning", () => {
              openSection("updates-section");
            });
          } else if (!silent) {
            showToast(state === "none" ? t("settingsPage.storeUpToDate") : t("settingsPage.storeUnavailable"), state === "none" ? "success" : "warning");
          }
          return;
        }
        // Un retour en arrière (Bêta -> Stable) est un choix de l'utilisateur,
        // pas une nouveauté : pas de toast d'alerte non sollicité à chaque
        // ouverture de la page, la carte ci-dessous suffit.
        if (info.has_update && info.is_downgrade && silent) {
          // rien : voir commentaire ci-dessus
        } else if (info.has_update) {
          showToast(
            `${t("settingsPage.updateAvailable")} (${info.latest_version})`,
            "warning",
            () => {
              openSection("updates-section");
            },
          );
        } else if (!silent) {
          if (info.online) {
            showToast(t("settingsPage.upToDate"), "success");
          } else {
            showToast(info.message || t("settingsPage.updateError"), "warning");
          }
        }
      } else if (!silent) {
        showToast(t("settingsPage.updateError"), "error");
      }
    } catch {
      if (!silent) showToast(t("settingsPage.updateError"), "error");
    } finally {
      setCheckingUpdate(false);
    }
  };

  // Build Google Play : déclenche l'action demandée (mise à jour souple, installation, fiche Google Play).
  const handleStoreAction = async (action: "start" | "complete" | "open") => {
    setStoreBusy(true);
    try {
      const res = await fetch(getApiUrl(`/updates/store/${action}`), { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        showToast(typeof body?.detail === "string" ? body.detail : t("settingsPage.storeActionError"), "error");
        return;
      }
      if (action === "start") showToast(t("settingsPage.storeStarted"), "success");
      if (action !== "open") await checkForUpdates(true);
    } catch {
      showToast(t("settingsPage.storeActionError"), "error");
    } finally {
      setStoreBusy(false);
    }
  };

  // Pendant le téléchargement par Google Play, relit l'état toutes les 5 s pour proposer « Redémarrer » dès qu'il est prêt.
  const storeDownloading = updateInfo?.store?.state === "downloading";
  useEffect(() => {
    if (!storeDownloading) return;
    const timer = setInterval(() => { void checkForUpdates(true); }, 5000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seule la présence d'un téléchargement en cours compte
  }, [storeDownloading]);

  // Notification proactive : vérifie une fois à l'ouverture des Réglages, sans
  // attendre un clic manuel sur "Rechercher une mise à jour" — silencieux
  // sauf si une mise à jour est réellement trouvée (cf. paramètre `silent`
  // ci-dessus).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- vérification ponctuelle contre une API externe (GitHub via le backend), pas un calcul dérivable au rendu
    checkForUpdates(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule vérification au montage, volontairement indépendante des re-rendus de checkForUpdates
  }, []);

  const handleApplyUpdate = async () => {
    const confirmText = updateInfo?.is_downgrade
      ? t("settingsPage.confirmDowngrade", { version: updateInfo.latest_version ?? "" })
      : t("settingsPage.applyUpdate") + " ?";
    if (!window.confirm(confirmText)) return;
    setApplyingUpdate(true);
    try {
      const res = await fetch(getApiUrl("/updates/apply"), { method: "POST" });
      if (res.ok) {
        // Le succès RÉEL (ou l'échec) est désormais suivi en direct par
        // <UpdateProgressOverlay/> (montée globalement dans ClientLayout,
        // WebSocket "update_progress") — ce toast ne fait plus que
        // confirmer le DÉCLENCHEMENT, jamais l'issue. Avant ce correctif,
        // ce même message ("Mise à jour téléchargée...") s'affichait ici
        // dès cette réponse HTTP, avant même que le téléchargement n'ait
        // commencé côté serveur — un échec réel (réseau coupé, checkout
        // git refusé, installeur annulé) restait alors invisible.
        showToast(t("settingsPage.updateInProgressHint"));
      } else if (res.status === 409) {
        showToast(t("settingsPage.updateAlreadyInProgress"), "warning");
      } else {
        const body = await res.json().catch(() => null);
        showToast(body?.detail || t("settingsPage.updateError"), "error");
      }
    } catch {
      showToast(t("settingsPage.updateError"), "error");
    } finally {
      setApplyingUpdate(false);
    }
  };

  const [torCheck, setTorCheck] = useState<{ ok: boolean; source?: string; error?: string } | null>(null);
  const [torChecking, setTorChecking] = useState(false);
  const handleTorCheck = async () => {
    if (!data) return;
    setTorChecking(true);
    setTorCheck(null);
    try {
      const res = await fetch(getApiUrl("/updates/tor-check"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proxy: data.update_tor_proxy }),
      });
      const body = await res.json().catch(() => ({}));
      setTorCheck(res.ok ? body : { ok: false, error: body.detail || t("settingsPage.saveError") });
    } catch {
      setTorCheck({ ok: false, error: t("common.networkError") });
    } finally {
      setTorChecking(false);
    }
  };

  const handleAutoUpdateChange = async (patch: {
    auto_update_enabled?: "true" | "false";
    auto_update_time?: string;
    update_tor?: "true" | "false";
    update_tor_proxy?: string;
  }) => {
    if (!data) return;
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (res.ok) {
        setData(await res.json());
        showToast(t("settingsPage.autoUpdateSaved"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("settingsPage.saveError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  // Canal de mise à jour (Stable/Bêta/Canary) : bascule
  // immédiate (comme le thème/la langue), pas de bouton "Enregistrer" séparé
  // — un choix à 3 états sans état intermédiaire à valider. Relance
  // aussitôt checkForUpdates() pour que la carte "Mises à jour" reflète tout
  // de suite le nouveau canal plutôt que de garder l'ancien résultat affiché
  // jusqu'au prochain clic manuel sur "Rechercher une mise à jour".
  const handleChannelChange = async (channel: UpdateChannel) => {
    if (!data || data.update_channel === channel || changingChannel) return;
    setChangingChannel(true);
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ update_channel: channel }),
      });
      if (res.ok) {
        setData(await res.json());
        showToast(t(isRollingReleaseChannel(channel) ? "settingsPage.updateChannelJoined" : "settingsPage.updateChannelLeft", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(channel)}`) }));
        checkForUpdates();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("settingsPage.saveError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setChangingChannel(false);
    }
  };

  const handleSaveLogsRetention = async (days: number) => {
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ logs_retention_days: days }),
      });
      if (res.ok) {
        showToast(t("settingsPage.retentionSaved"), "success");
      } else {
        showToast(t("settingsPage.saveError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const handlePurgeLogs = async () => {
    if (!window.confirm(t("settingsPage.purgeConfirm"))) return;
    setIsPurgingLogs(true);
    try {
      const res = await fetch(getApiUrl("/settings/logs/purge"), { method: "POST" });
      const body = await res.json();
      if (res.ok) {
        const details = body.details;
        const msg = details
          ? t("settingsPage.purgeDone", { logs: details.purged_logs, metrics: details.purged_metrics })
          : (body.message || t("settingsPage.logsPurgedSuccess"));
        showToast(msg, "success");
      } else {
        showToast(body.detail || t("settingsPage.saveError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setIsPurgingLogs(false);
    }
  };

  const handleCopyPath = async (p: string) => {
    // « Copié » seulement si la copie a réellement réussi ; sinon l'adresse est affichée pour être
    // copiée à la main (cf. lib/clipboard.ts : HTTP simple sur l'IP locale = pas d'API presse-papiers).
    if (await copyText(p)) {
      showToast(t("settingsPage.paths.pathCopied"));
    } else {
      showToast(p);
    }
  };

  const handleOpenPath = async (p: string) => {
    try {
      const res = await fetch(getApiUrl("/settings/open-path"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: p }),
      });
      const resData = await res.json().catch(() => ({}));
      if (res.ok) {
        if (resData.status === "android") {
          await copyText(p);
          showToast(resData.message || t("settingsPage.paths.pathCopied"));
        } else {
          showToast(t("settingsPage.paths.folderOpened"));
        }
      } else {
        showToast(resData.detail || t("settingsPage.openFolderError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const handleExportBackup = () => {
    setExportingBackup(true);
    const url = getApiUrl("/settings/backup/export");
    const a = document.createElement("a");
    a.href = url;
    a.download = `bobine-backup-${new Date().toISOString().slice(0, 10)}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => setExportingBackup(false), 2000);
  };

  const handleSelectBackupFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedBackupFile(file);
      setShowRestoreConfirm(true);
    }
    e.target.value = "";
  };

  const handleRestoreBackup = async () => {
    if (!selectedBackupFile) return;
    setRestoringBackup(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedBackupFile);
      const res = await fetch(getApiUrl("/settings/backup/restore"), {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        showToast(t("settingsPage.restoreSuccess"), "success");
        setShowRestoreConfirm(false);
        setSelectedBackupFile(null);
      } else {
        const err = await res.json().catch(() => null);
        showToast(err?.detail || t("settingsPage.restoreError"), "error");
      }
    } catch {
      showToast(t("settingsPage.restoreError"), "error");
    } finally {
      setRestoringBackup(false);
    }
  };

  const resetDataReady = normalizePhrase(resetDataConfirm) === "REINITIALISER";

  const handleResetData = async () => {
    if (!resetDataReady) return;
    setResettingData(true);
    try {
      const res = await fetch(getApiUrl("/settings/system/reset-data"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: resetDataConfirm }),
      });
      if (res.ok) {
        showToast(t("settingsPage.resetDataSuccess"), "success");
        setShowResetData(false);
        setResetDataConfirm("");
      } else {
        const err = await res.json().catch(() => null);
        showToast(err?.detail || t("settingsPage.resetDataError"), "error");
      }
    } catch {
      showToast(t("settingsPage.resetDataError"), "error");
    } finally {
      setResettingData(false);
    }
  };

  const uninstallReady = normalizePhrase(uninstallConfirm) === "DESINSTALLER";

  if (loading) {
    return <div className="live-empty">{t("common.loading")}</div>;
  }
  if (!data) {
    return <div className="live-empty">{t("settingsPage.loadError")}</div>;
  }

  return (
    <div className="settings-page">
      {toast && (
        <div
          className={`toast ${toast.type} ${toast.onClick ? "clickable olc-press" : ""}`}
          onClick={toast.onClick}
          style={{ cursor: toast.onClick ? "pointer" : "default" }}
          role={toast.onClick ? "button" : undefined}
          tabIndex={toast.onClick ? 0 : undefined}
        >
          {toast.type === "warning" && <Icon name="system_update" size={18} color="var(--accent-text)" />}
          <span>{toast.message}</span>
          {toast.onClick && <Icon name="arrow_downward" size={16} />}
        </div>
      )}

      <PageNav
        tabs={SETTINGS_CATEGORIES.map((category) => ({ id: category.id, icon: category.icon, label: t(`settingsPage.cat.${category.id}.label`) }))}
        value={searching && matched.size > 0 ? [...matched][0] : category}
        onChange={(id) => chooseCategory(id as SettingsCategoryId)}
        ariaLabel={t("settingsPage.categoriesLabel")}
      />
      {/* Recherche : son propre espace, centré sous les catégories. */}
      <div className="settings-search-row">
        <label className="settings-search">
          <Icon name="search" size={18} />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("settingsPage.searchPlaceholder")}
            aria-label={t("settingsPage.searchPlaceholder")}
          />
        </label>
      </div>
      {searching && matched.size === 0 && <div className="live-empty">{t("settingsPage.searchNone")}</div>}

      {/* ---- Apparence : thèmes + langue ---- */}
      <section className="live-block" id="section-appearance" hidden={!shows("section-appearance")}>
        <h3><Icon name="palette" size={18} /> {t("settingsPage.appearanceSection")}</h3>
        <div className="form-group">
          <label className="form-label">{t("settingsPage.themeLabel")}</label>

          <SegmentedTabs
            ariaLabel={t("settingsPage.themeModeLabel")}
            value={themeMode}
            onChange={(id) => setThemeMode(id as ThemeMode)}
            tabs={THEME_MODES.map((mode) => ({
              id: mode,
              icon: mode === "auto" ? "brightness_auto" : mode === "light" ? "light_mode" : "dark_mode",
              label: t(`settingsPage.themeMode${mode === "auto" ? "Auto" : mode === "light" ? "Light" : "Dark"}`),
            }))}
          />
          <p className="settings-hint">{t("settingsPage.themeModeHint")}</p>

          {/* Les pastilles montrent la palette de chaque thème dans le mode appliqué en ce moment. */}
          <div className="theme-picker-grid">
            {THEMES.map((option) => {
              const palette = paletteOf(option.id, resolvedMode);
              return (
                <button
                  key={option.id}
                  type="button"
                  className={`theme-picker-card ${theme === option.id ? "active" : ""}`}
                  aria-pressed={theme === option.id}
                  onClick={() => setTheme(option.id)}
                >
                  <div className="theme-picker-swatch">
                    {[palette.bg, palette.surface, palette.accent, palette.text].map((color, i) => (
                      <span key={i} style={{ background: color }} />
                    ))}
                  </div>
                  <span className="theme-picker-name">{t(option.labelKey)}</span>
                </button>
              );
            })}
          </div>

          <p className="settings-hint">{t("settingsPage.themeHint")}</p>
        </div>

        <div className="form-group" style={{ maxWidth: "320px" }}>
          <label className="form-label">{t("settingsPage.glassLabel")}</label>
          <ResponsiveSelect
            className="form-control"
            value={glassMode}
            onChange={(value) => { setGlassMode(value as GlassMode); saveMode(value as GlassMode); }}
            title={t("settingsPage.glassLabel")}
            options={[
              { value: "auto", label: t("settingsPage.glassAuto") },
              { value: "full", label: t("settingsPage.glassFull") },
              { value: "reduced", label: t("settingsPage.glassReduced") },
              { value: "off", label: t("settingsPage.glassOff") },
            ]}
          />
          <p className="settings-hint">{t("settingsPage.glassHint")}</p>
        </div>

        <div className="form-group" style={{ maxWidth: "320px" }}>
          <label className="form-label">{t("settingsPage.languageLabel")}</label>
          <ResponsiveSelect
            className="form-control"
            value={storedLanguage}
            onChange={(value) => setLanguage(value as Language)}
            title={t("settingsPage.languageLabel")}
            options={[
              { value: "fr", label: t("settingsPage.languageFr") },
              { value: "en", label: t("settingsPage.languageEn") },
            ]}
          />
          <p className="settings-hint">{t("settingsPage.languageHint")}</p>
          {languagePending && (
            <div className="settings-hint" role="status" style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
              <span>{t("settingsPage.languagePending", { language: storedLanguage === "fr" ? t("settingsPage.languageFr") : t("settingsPage.languageEn") })}</span>
              <button type="button" className="btn btn-secondary" onClick={() => void restartNow()} disabled={restarting}>
                {t("settingsPage.languageRestartNow")}
              </button>
              {data && data.restart_guaranteed === false && <span>{t("settingsPage.restartNotGuaranteed")}</span>}
              {restartMessage && <span>{restartMessage}</span>}
            </div>
          )}
        </div>

        <div className="form-group" style={{ maxWidth: "520px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "16px", flexWrap: "wrap" }}>
            <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>{t("settingsPage.simplifiedUiLabel")}</span>
            <label className="ra-switch" title={t("settingsPage.simplifiedUiLabel")}>
              <input type="checkbox" checked={simplifiedUi} onChange={(e) => setSimplifiedUi(e.target.checked)} />
              <span className="ra-switch-track" />
            </label>
          </div>
          <p className="settings-hint">{t("settingsPage.simplifiedUiHint")}</p>
        </div>
      </section>

      {/* ---- Sortie câblée : Pupitre Studio (/grid) vs Headless (Écran physique & HDMI) ---- */}
      <section className="live-block" id="section-display" hidden={!shows("section-display")}>
        <h3><Icon name="tv" size={18} /> {t("settingsPage.wiredDisplaySection")}</h3>
        <p className="settings-hint" style={{ marginTop: "-8px", marginBottom: "16px" }}>
          {t("settingsPage.wiredDisplaySubtitle")}
        </p>

        <div className="form-group">
          <label className="form-label">{t("settingsPage.wiredDisplayModeLabel")}</label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px", marginTop: "8px" }}>
            {/* Option 0 : Automatique (dérivé des écrans externes réellement connectés) */}
            <button
              type="button"
              className={`theme-picker-card ${displayModeSetting === "auto" ? "active" : ""}`}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "16px",
                textAlign: "left",
                height: "auto",
                gap: "8px",
              }}
              onClick={() => {
                setDisplayModeSetting("auto");
                showToast(t("settingsPage.savedToast"), "success");
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                <div style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "var(--radius-sm)",
                  background: displayModeSetting === "auto" ? "var(--accent-primary)" : "var(--bg-surface-hover)",
                  color: displayModeSetting === "auto" ? "var(--accent-primary-fg)" : "var(--text-main)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Icon name="autorenew" size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <strong style={{ display: "block", fontSize: "0.95rem" }}>
                    {t("settingsPage.wiredDisplayModeAuto")}
                  </strong>
                </div>
                {displayModeSetting === "auto" && (
                  <span style={{ color: "var(--accent-text)", display: "flex", alignItems: "center" }}>
                    <Icon name="check_circle" size={18} />
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                {t("settingsPage.wiredDisplayModeAutoDesc")}
              </p>
              <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--accent-text)", lineHeight: 1.4 }}>
                {displayExternalCount === null
                  ? t("settingsPage.wiredDisplayAutoNoReport")
                  : t("settingsPage.wiredDisplayAutoDetected", {
                      count: displayExternalCount,
                      mode: wiredDisplayMode === "dual_screen" ? t("settingsPage.wiredDisplayModeDual") : t("settingsPage.wiredDisplayModeHeadless"),
                    })}
              </p>
            </button>

            {/* Option 1 : Headless (Affichage Classique / mini-PC autonome) */}
            <button
              type="button"
              className={`theme-picker-card ${displayModeSetting === "headless" ? "active" : ""}`}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "16px",
                textAlign: "left",
                height: "auto",
                gap: "8px",
              }}
              onClick={() => {
                setDisplayModeSetting("headless");
                showToast(t("settingsPage.savedToast"), "success");
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                <div style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "var(--radius-sm)",
                  background: displayModeSetting === "headless" ? "var(--accent-primary)" : "var(--bg-surface-hover)",
                  color: displayModeSetting === "headless" ? "var(--accent-primary-fg)" : "var(--text-main)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Icon name="desktop_windows" size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <strong style={{ display: "block", fontSize: "0.95rem" }}>
                    {t("settingsPage.wiredDisplayModeHeadless")}
                  </strong>
                </div>
                {displayModeSetting === "headless" && (
                  <span style={{ color: "var(--accent-text)", display: "flex", alignItems: "center" }}>
                    <Icon name="check_circle" size={18} />
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                {t("settingsPage.wiredDisplayModeHeadlessDesc")}
              </p>
            </button>

            {/* Option 2 : Pupitre Studio + Vidéo HDMI */}
            <button
              type="button"
              className={`theme-picker-card ${displayModeSetting === "dual_screen" ? "active" : ""}`}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "16px",
                textAlign: "left",
                height: "auto",
                gap: "8px",
              }}
              onClick={() => {
                setDisplayModeSetting("dual_screen");
                showToast(t("settingsPage.savedToast"), "success");
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                <div style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "var(--radius-sm)",
                  background: displayModeSetting === "dual_screen" ? "var(--accent-primary)" : "var(--bg-surface-hover)",
                  color: displayModeSetting === "dual_screen" ? "var(--accent-primary-fg)" : "var(--text-main)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Icon name="view_quilt" size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <strong style={{ display: "block", fontSize: "0.95rem" }}>
                    {t("settingsPage.wiredDisplayModeDual")}
                  </strong>
                </div>
                {displayModeSetting === "dual_screen" && (
                  <span style={{ color: "var(--accent-text)", display: "flex", alignItems: "center" }}>
                    <Icon name="check_circle" size={18} />
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                {t("settingsPage.wiredDisplayModeDualDesc")}
              </p>
            </button>
          </div>

          {/* Note explicite sur le périmètre de /grid (canal câblé uniquement) */}
          <div
            style={{
              marginTop: "12px",
              padding: "12px 16px",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--radius-md)",
              display: "flex",
              alignItems: "flex-start",
              gap: "12px",
            }}
          >
            <div style={{ color: "var(--accent-text)", marginTop: "1px", flexShrink: 0 }}>
              <Icon name="info" size={20} />
            </div>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
              {t("settingsPage.wiredDisplayGridCableOnlyNote")}
            </p>
          </div>

          {/* Liens d'accès direct au mode Pupitre Studio & Écran Vidéo */}
          {wiredDisplayMode === "dual_screen" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "16px" }} className="olc-anim-in">
              {/* Carte 1 : Pupitre Studio */}
              <a
                href="/grid"
                target="_blank"
                rel="noopener noreferrer"
                className="wired-display-action-card olc-card-hover"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-surface-elevated)",
                  border: "1px solid var(--border-color)",
                  textDecoration: "none",
                  color: "inherit",
                  gap: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <div style={{
                    width: "42px",
                    height: "42px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--accent-primary)",
                    color: "var(--accent-primary-fg)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}>
                    <Icon name="touch_app" size={22} />
                  </div>
                  <div>
                    <strong style={{ display: "block", fontSize: "0.98rem", color: "var(--text-main)", marginBottom: "3px" }}>
                      {t("settingsPage.wiredDisplayOpenGrid")}
                    </strong>
                    <span style={{ fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                      {t("settingsPage.wiredDisplayOpenGridDesc")}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-text)", fontWeight: 700, fontSize: "0.9rem", flexShrink: 0 }}>
                  <span>{t("settingsPage.wiredDisplayOpenGrid")}</span>
                  <Icon name="open_in_new" size={16} />
                </div>
              </a>

              {/* Carte 2 : Écran Vidéo HDMI */}
              <a
                href="/cinema"
                target="_blank"
                rel="noopener noreferrer"
                className="wired-display-action-card olc-card-hover"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-surface-elevated)",
                  border: "1px solid var(--border-color)",
                  textDecoration: "none",
                  color: "inherit",
                  gap: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <div style={{
                    width: "42px",
                    height: "42px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--bg-surface-hover)",
                    color: "var(--text-main)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}>
                    <Icon name="tv" size={22} />
                  </div>
                  <div>
                    <strong style={{ display: "block", fontSize: "0.98rem", color: "var(--text-main)", marginBottom: "3px" }}>
                      {t("settingsPage.wiredDisplayOpenCinema")}
                    </strong>
                    <span style={{ fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                      {t("settingsPage.wiredDisplayOpenCinemaDesc")}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-text)", fontWeight: 700, fontSize: "0.9rem", flexShrink: 0 }}>
                  <span>{t("settingsPage.wiredDisplayOpenCinema")}</span>
                  <Icon name="open_in_new" size={16} />
                </div>
              </a>
            </div>
          )}

          {/* Contrôle du capot (PC Portable / Clamshell) */}
          {lidInfo?.has_lid && (
            <div
              style={{
                marginTop: "16px",
                padding: "16px 20px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-surface-elevated)",
                border: "1px solid var(--border-color)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "16px",
                flexWrap: "wrap",
              }}
            >
              <div style={{ flex: "1 1 280px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, fontSize: "0.95rem", color: "var(--text-main)" }}>
                  <Icon name="laptop" size={20} />
                  <span>{t("settingsPage.clamshellToggle")}</span>
                </div>
                <p className="settings-hint" style={{ margin: "4px 0 0 28px", fontSize: "0.85rem" }}>
                  {t("settingsPage.clamshellDesc")}
                </p>
              </div>
              <div
                style={{
                  display: "inline-flex",
                  borderRadius: "var(--radius-md)",
                  overflow: "hidden",
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-surface-elevated)",
                }}
              >
                <button
                  type="button"
                  className={`btn btn-sm ${lidInfo.prevent_sleep ? "btn-primary" : "btn-secondary"}`}
                  style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                  onClick={() => handleToggleLid(true)}
                  disabled={updatingLid}
                >
                  {t("common.yes")}
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${!lidInfo.prevent_sleep ? "btn-primary" : "btn-secondary"}`}
                  style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                  onClick={() => handleToggleLid(false)}
                  disabled={updatingLid}
                >
                  {t("common.no")}
                </button>
              </div>
            </div>
          )}

          {/* Astuce tablette sur profil Android */}
          {data?.deployment_profile === "android" && (
            <p className="settings-hint" style={{ marginTop: "12px" }}>
              {t("settingsPage.wiredDisplayTabletHint")}
            </p>
          )}
        </div>
      </section>

      {/* ---- Branding : image de marque & logo ---- */}
      <section className="live-block" id="section-branding" hidden={!shows("section-branding")}>
        <h3><Icon name="image" size={18} /> {t("settingsPage.brandingSection")}</h3>
        <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "24px", flexWrap: "wrap" }}>
          {/* Cadre de prévisualisation : dimensions généreuses et padding pour contenir tout logo */}
          <div
            style={{
              width: "180px",
              height: "84px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--radius-md)",
              padding: "10px",
              flexShrink: 0,
              overflow: "hidden",
            }}
          >
            <AppLogo size={54} />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", flexGrow: 1, minWidth: "260px" }}>
            {/* Commutateur de logo (quand un logo personnalisé a été uploadé) */}
            {hasCustomLogo && (
              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <span className="form-label" style={{ margin: 0, fontSize: "0.85rem" }}>
                  {t("settingsPage.activeLogoLabel")}
                </span>
                <div
                  style={{
                    display: "inline-flex",
                    borderRadius: "var(--radius-md)",
                    overflow: "hidden",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-surface-elevated)",
                  }}
                >
                  <button
                    type="button"
                    className={`btn btn-sm ${activeLogo === "default" ? "btn-primary" : "btn-secondary"}`}
                    style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
                    onClick={() => setActiveLogo("default")}
                  >
                    {t("settingsPage.logoBobine")}
                  </button>
                  <button
                    type="button"
                    className={`btn btn-sm ${activeLogo === "custom" ? "btn-primary" : "btn-secondary"}`}
                    style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
                    onClick={() => setActiveLogo("custom")}
                  >
                    {t("settingsPage.logoCustom")}
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
              <label className="btn btn-secondary" style={{ height: "38px", cursor: uploadingLogo ? "wait" : "pointer" }}>
                <Icon name="upload" size={16} /> {hasCustomLogo ? t("settingsPage.logoUploadReplace") : t("settingsPage.logoUploadLabel")}
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  style={{ display: "none" }}
                  disabled={uploadingLogo}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleLogoUpload(file);
                    e.target.value = "";
                  }}
                />
              </label>

              {hasCustomLogo && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ height: "38px", color: "var(--accent-error-text)" }}
                  onClick={() => {
                    if (window.confirm(t("settingsPage.logoDeleteConfirm"))) {
                      handleLogoReset();
                    }
                  }}
                  disabled={uploadingLogo}
                  title={t("settingsPage.logoDeleteButton")}
                >
                  <Icon name="delete" size={16} /> {t("settingsPage.logoDeleteButton")}
                </button>
              )}
            </div>

            <p className="settings-hint" style={{ margin: 0 }}>
              {t("settingsPage.logoHint")}
            </p>
          </div>
        </div>
      </section>


      {/* ---- Mises à jour logicielles ---- */}
      <section className="live-block" id="updates-section" hidden={!shows("updates-section")}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <h3 style={{ margin: 0 }}>
            <Icon name="system_update" size={18} /> {t("settingsPage.updatesSection")}
          </h3>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: "40px", padding: "6px 16px" }}
            onClick={() => checkForUpdates()}
            disabled={checkingUpdate || applyingUpdate}
          >
            <Icon
              name="sync"
              size={16}
              className={checkingUpdate ? "olc-spin" : ""}
            />
            {checkingUpdate ? t("settingsPage.checkingUpdates") : t("settingsPage.checkUpdates")}
          </button>
        </div>
        <p className="settings-hint" style={{ marginTop: "4px" }}>
          {t("settingsPage.updatesHint")}
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "8px" }}>
          {/* Version actuelle */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>
              {t("settingsPage.currentVersion")} :
            </span>
            <span className="update-badge">
              <strong>{updateInfo?.current_version ?? "…"}</strong>
              {updateInfo?.current_commit && updateInfo.current_commit !== "unknown" && (
                <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "0.75rem", opacity: 0.8 }}>
                  ({updateInfo.current_commit})
                </span>
              )}
            </span>
            {updateInfo?.checked_at && (
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                {t("settingsPage.lastChecked")} : {new Date(updateInfo.checked_at).toLocaleTimeString()}
              </span>
            )}
          </div>

          {!data.store_managed && (
            <>
          {/* Canal de mise à jour */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
            <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
              {t("settingsPage.updateChannelLabel")}
            </span>
            <div
              style={{
                display: "inline-flex",
                borderRadius: "var(--radius-md)",
                overflow: "hidden",
                border: "1px solid var(--border-color)",
                background: "var(--bg-surface-elevated)",
              }}
            >
              {RELEASE_CHANNELS.map((channel) => (
                <button
                  key={channel}
                  type="button"
                  className={`btn btn-sm ${data.update_channel === channel ? "btn-primary" : "btn-secondary"}`}
                  style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: "6px" }}
                  onClick={() => {
                    if (!isRollingReleaseChannel(channel)) handleChannelChange(channel);
                    else if (data.update_channel !== channel) setConfirmingChannel(channel);
                  }}
                  disabled={changingChannel}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={channelLogoUrl(channel)} alt="" width={18} height={18} style={{ borderRadius: "4px" }} />
                  {t(`settingsPage.updateChannel${channelI18nSuffix(channel)}`)}
                </button>
              ))}
            </div>
          </div>
          <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.updateChannelHint")}</p>
          {data.update_tor_supported && (
            <>
              {/* Mises à jour par Tor */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
                <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
                  {t("settingsPage.updateTorLabel")}
                </span>
                <label className="ra-switch" title={t("settingsPage.updateTorLabel")}>
                  <input
                    type="checkbox"
                    checked={data.update_tor === "true"}
                    onChange={(e) => handleAutoUpdateChange({ update_tor: e.target.checked ? "true" : "false" })}
                  />
                  <span className="ra-switch-track" />
                </label>
              </div>
              {data.update_tor === "true" && (
                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                  <label htmlFor="update-tor-proxy" className="form-label" style={{ margin: 0 }}>
                    {t("settingsPage.updateTorProxyLabel")}
                  </label>
                  <input
                    id="update-tor-proxy"
                    type="text"
                    className="form-control"
                    style={{ maxWidth: "200px" }}
                    value={data.update_tor_proxy ?? ""}
                    spellCheck={false}
                    onChange={(e) => setData({ ...data, update_tor_proxy: e.target.value })}
                    onBlur={(e) => handleAutoUpdateChange({ update_tor_proxy: e.target.value.trim() })}
                  />
                  <button type="button" className="btn btn-secondary btn-sm" disabled={torChecking} onClick={handleTorCheck}>
                    <Icon name={torChecking ? "sync" : "verified_user"} size={16} className={torChecking ? "olc-spin" : ""} />
                    {t(torChecking ? "settingsPage.updateTorChecking" : "settingsPage.updateTorCheck")}
                  </button>
                  {torCheck && (
                    <span role="status" style={{ color: torCheck.ok ? "var(--accent-success, #2e7d32)" : "var(--accent-warning, #c77700)" }}>
                      {torCheck.ok
                        ? t(torCheck.source === "on_demand" ? "settingsPage.updateTorOkOnDemand" : "settingsPage.updateTorOk")
                        : t("settingsPage.updateTorFailed", { error: torCheck.error ?? "" })}
                    </span>
                  )}
                </div>
              )}
              <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.updateTorHint")}</p>
            </>
          )}
            </>
          )}

          {data.store_managed && (
            <div className="olc-anim-in" style={{ display: "flex", flexDirection: "column", gap: "12px", width: "100%", maxWidth: "620px" }}>
              <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeManagedHint")}</p>
              <div className="update-card-banner" style={{ borderLeft: "4px solid var(--accent-text)", boxShadow: "var(--shadow-sm)", display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700 }}>
                  <Icon
                    name={updateInfo?.store?.state === "available" || updateInfo?.store?.state === "downloaded" ? "system_update" : updateInfo?.store?.state === "failed" ? "error" : "check_circle"}
                    size={18}
                  />
                  <span>
                    {updateInfo?.store?.state === "none" && t("settingsPage.storeUpToDate")}
                    {updateInfo?.store?.state === "available" && `${t("settingsPage.storeAvailable")}${updateInfo.store.version_code ? ` (build ${updateInfo.store.version_code})` : ""}`}
                    {updateInfo?.store?.state === "downloading" && t("settingsPage.storeDownloading")}
                    {updateInfo?.store?.state === "downloaded" && t("settingsPage.storeDownloaded")}
                    {updateInfo?.store?.state === "installing" && t("settingsPage.storeInstalling")}
                    {updateInfo?.store?.state === "failed" && t("settingsPage.storeFailed")}
                    {(!updateInfo?.store || updateInfo.store.state === "unavailable") && (updateInfo?.store?.message || t("settingsPage.storeUnavailable"))}
                  </span>
                </div>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  {updateInfo?.store?.state === "available" && (
                    <button type="button" className="btn btn-primary" disabled={storeBusy} onClick={() => handleStoreAction("start")}>
                      <Icon name="system_update" size={16} /> {t("settingsPage.storeUpdateButton")}
                    </button>
                  )}
                  {updateInfo?.store?.state === "downloaded" && (
                    <button type="button" className="btn btn-primary" disabled={storeBusy} onClick={() => handleStoreAction("complete")}>
                      <Icon name="restart_alt" size={16} /> {t("settingsPage.storeRestartButton")}
                    </button>
                  )}
                  <button type="button" className="btn btn-secondary" disabled={storeBusy} onClick={() => handleStoreAction("open")}>
                    <Icon name="storefront" size={16} /> {t("settingsPage.storeOpenButton")}
                  </button>
                </div>
              </div>
              <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeAutoHint")}</p>
              <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeBetaHint")}</p>
            </div>
          )}
          {!data.store_managed && data.auto_update_supported !== false && (
            <>
          {/* Mise à jour automatique planifiée */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
            <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
              {t("settingsPage.autoUpdateSection")}
            </span>
            <label className="ra-switch" title={t("settingsPage.autoUpdateToggleLabel")}>
              <input
                type="checkbox"
                checked={data.auto_update_enabled === "true"}
                onChange={(e) => handleAutoUpdateChange({ auto_update_enabled: e.target.checked ? "true" : "false" })}
              />
              <span className="ra-switch-track" />
            </label>
          </div>
          {data.auto_update_enabled === "true" && (
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <label htmlFor="auto-update-time" className="form-label" style={{ margin: 0 }}>
                {t("settingsPage.autoUpdateTimeLabel")}
              </label>
              <input
                id="auto-update-time"
                type="time"
                className="form-control"
                style={{ maxWidth: "140px" }}
                value={data.auto_update_time}
                onChange={(e) => setData({ ...data, auto_update_time: e.target.value })}
                onBlur={(e) => handleAutoUpdateChange({ auto_update_time: e.target.value })}
              />
            </div>
          )}
          <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.autoUpdateToggleHint")}</p>
            </>
          )}

          {/* Résultat de la recherche */}
          {updateInfo && !updateInfo.store_managed && (
            <div className="olc-anim-in" style={{ marginTop: "4px" }}>
              {updateInfo.has_update ? (
                <div
                  className="update-card-banner"
                  style={{
                    borderLeft: "4px solid var(--accent-text)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="update-badge alert">
                        <Icon name="campaign" size={14} />
                        {updateInfo.is_downgrade ? t("settingsPage.downgradeAvailable") : t("settingsPage.updateAvailable")}
                      </span>
                      <strong style={{ fontSize: "0.95rem" }}>{updateInfo.latest_version}</strong>
                    </div>
                    {updateInfo.html_url && (
                      <a
                        href={updateInfo.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-secondary btn-sm"
                        style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px" }}
                      >
                        <Icon name="open_in_new" size={14} /> {t("settingsPage.viewOnGithub")}
                      </a>
                    )}
                  </div>

                  <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--text-main)" }}>
                    {updateInfo.is_downgrade
                      ? t("settingsPage.downgradeDetail")
                      : updateInfo.release_title || t("settingsPage.updateAvailableDetail")}
                  </p>

                  {updateInfo.release_notes && (
                    <div>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ marginBottom: "8px" }}
                        onClick={() => setShowReleaseNotes((v) => !v)}
                      >
                        <Icon name={showReleaseNotes ? "expand_less" : "expand_more"} size={16} />
                        {t("settingsPage.releaseNotes")}
                      </button>
                      {showReleaseNotes && (
                        <div className="update-notes-box olc-anim-in">
                          <MarkdownView content={updateInfo.release_notes} />
                        </div>
                      )}
                    </div>
                  )}

                  <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "4px" }}>
                    {updateInfo.can_auto_apply ? (
                      <button
                        type="button"
                        className="btn btn-primary"
                        style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px" }}
                        onClick={handleApplyUpdate}
                        disabled={applyingUpdate}
                      >
                        {applyingUpdate ? (
                          <>
                            <Icon name="sync" size={16} className="olc-spin" />
                            {t("settingsPage.applyingUpdate")}
                          </>
                        ) : (
                          <>
                            <Icon name="download" size={16} />
                            {updateInfo.is_downgrade ? t("settingsPage.applyDowngrade") : t("settingsPage.applyUpdate")}
                          </>
                        )}
                      </button>
                    ) : (
                      <a
                        href={updateInfo.download_url || updateInfo.html_url || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-primary"
                        style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px", textDecoration: "none" }}
                      >
                        <Icon name="download" size={16} />
                        {updateInfo.asset_name
                          ? `${t("settingsPage.downloadUpdate")} (${updateInfo.asset_name}${updateInfo.asset_size ? ` - ${formatBytes(updateInfo.asset_size)}` : ""})`
                          : t("settingsPage.downloadUpdate")}
                      </a>
                    )}
                  </div>
                </div>
              ) : updateInfo.online ? (
                <div
                  className="update-card-banner"
                  style={{
                    borderLeft: "4px solid var(--accent-text)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="update-badge success">
                      <Icon name="check_circle" size={14} />
                      {t("settingsPage.upToDate")}
                    </span>
                    <span style={{ fontSize: "0.9rem", color: "var(--text-main)" }}>
                      {t("settingsPage.upToDateDetail")}
                    </span>
                  </div>
                </div>
              ) : (
                <div
                  className="update-card-banner"
                  style={{ borderLeft: "4px solid var(--border-color)" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-muted)" }}>
                    <Icon name={updateInfo.error_code === "offline" || !updateInfo.error_code ? "wifi_off" : "info"} size={16} />
                    <span style={{ fontSize: "0.85rem" }}>
                      {updateInfo.message || t("settingsPage.updateError")}
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ---- Compatibilité navigateur (diagnostic local) ---- */}
      <div id="section-playback" hidden={!shows("section-playback")}>
      <BrowserCompatibility />

      {/* ---- Composant audio natif (expérimental, désactivé par défaut) ---- */}
      <MediaNativeSetting />
      </div>

      {/* ---- Sauvegarde & Restauration universelle ---- */}
      <section className="live-block" id="section-backup" hidden={!shows("section-backup")}>
        <h3><Icon name="archive" size={18} /> {t("settingsPage.backupSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.backupHint")}</p>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: "44px", display: "inline-flex", alignItems: "center", gap: "8px" }}
            onClick={handleExportBackup}
            disabled={exportingBackup}
          >
            <Icon name="download" size={16} />
            {exportingBackup ? t("settingsPage.exportingBackup") : t("settingsPage.exportBackup")}
          </button>

          <label
            className="btn btn-secondary"
            style={{ minHeight: "44px", display: "inline-flex", alignItems: "center", gap: "8px", cursor: "pointer", margin: 0 }}
          >
            <Icon name="upload" size={16} />
            {t("settingsPage.restoreBackup")}
            <input
              type="file"
              accept=".zip"
              style={{ display: "none" }}
              onChange={handleSelectBackupFile}
            />
          </label>
        </div>
      </section>

      {/* ---- Maintenance : resync ---- */}
      <section className="live-block" id="section-sync" hidden={!shows("section-sync")}>
        <h3><Icon name="sync" size={18} /> {t("settingsPage.syncSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.syncHint")}</p>
        <button type="button" className="btn btn-secondary" style={{ height: "44px", alignSelf: "flex-start" }} onClick={() => setShowResetConfirm(true)}>
          <Icon name="sync" size={16} /> {t("settingsPage.syncResetButton")}
        </button>
      </section>

      {/* ---- Maintenance : Nettoyage des journaux & métriques ---- */}
      <section className="live-block" id="section-logs" hidden={!shows("section-logs")}>
        <h3><Icon name="auto_delete" size={18} /> {t("settingsPage.logsMaintenanceSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.logsMaintenanceHint")}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            <label style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-main)" }}>
              {t("settingsPage.logsRetentionDaysLabel")} :
            </label>
            <input
              type="number"
              min={1}
              max={365}
              value={logsRetentionDays}
              onChange={(e) => setLogsRetentionDays(Math.max(1, parseInt(e.target.value) || 1))}
              onBlur={() => handleSaveLogsRetention(logsRetentionDays)}
              style={{
                width: "80px",
                padding: "6px 10px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-color)",
                background: "var(--bg-surface-elevated)",
                color: "var(--text-main)",
                fontSize: "0.95rem",
                fontWeight: 700,
                textAlign: "center",
              }}
            />
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {t("settingsPage.logsRetentionDaysHint")}
            </span>
          </div>
          <div>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ height: "42px", display: "inline-flex", alignItems: "center", gap: "8px" }}
              onClick={handlePurgeLogs}
              disabled={isPurgingLogs}
            >
              <Icon name="delete_sweep" size={18} />
              {isPurgingLogs ? t("settingsPage.logsPurging") : t("settingsPage.logsPurgeNow")}
            </button>
          </div>
        </div>
      </section>

      <div id="section-diagnostics" hidden={!shows("section-diagnostics")}>
      <ImportDiagnosticsPanel />
      </div>

      <div id="section-startup" hidden={!shows("section-startup")}>
      <StartOnBootToggle />
      </div>

      {/* ---- Documentation : chemins (lecture seule) ---- */}
      <section className="live-block" id="section-docs" hidden={!shows("section-docs")}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <h3 style={{ margin: 0 }}><Icon name="description" size={18} /> {t("settingsPage.docSection")}</h3>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: "36px", padding: "4px 14px", fontSize: "0.85rem", display: "inline-flex", alignItems: "center", gap: "6px" }}
            onClick={() => fetchSettings(true)}
            disabled={refreshingNetwork}
          >
            <Icon name="sync" size={16} className={refreshingNetwork ? "olc-spin" : ""} />
            <span>{refreshingNetwork ? t("settingsPage.refreshingNetwork") : t("settingsPage.refreshNetwork")}</span>
          </button>
        </div>
        <p className="settings-hint" style={{ marginTop: "4px" }}>{t("settingsPage.docHint")}</p>

        {/* 1. Accès Local (boucle locale 127.0.0.1) */}
        <details className="settings-doc-group" open={!isMobile}>
          <summary className="settings-doc-header">
            <Icon name="tv" size={18} />
            <span>{t("settingsPage.paths.localHeading")}</span>
          </summary>
          <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.localHint")}</p>
          <AddressList
            base={`http://127.0.0.1:${data.network.port}`}
            pages={data.deployment_profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS}
            t={t}
            onCopy={handleCopyPath}
            copyLabel={t("settingsPage.paths.copyPath")}
          />
        </details>

        {/* 2. Accès Réseau (LAN / Wi-Fi) */}
        <details className="settings-doc-group" open={true}>
          <summary className="settings-doc-header">
            <Icon name="wifi" size={18} />
            <span>{t("settingsPage.paths.networkHeading")}</span>
          </summary>
          <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.networkHint")}</p>
          {(data.network.access ?? []).filter((link) => link.kind === "lan" || link.kind === "vpn").length === 0 && (
            <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.localIpUnavailable")}</p>
          )}
          {(data.network.access ?? [])
            .filter((link) => link.kind !== "loopback")
            .map((link) => (
              <div key={link.url} style={{ marginTop: "10px" }}>
                <div className="settings-path-key" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Icon name={link.kind === "vpn" ? "vpn_lock" : link.kind === "mdns" ? "dns" : "lan"} size={16} />
                  {link.kind === "mdns"
                    ? t("settingsPage.paths.mdnsUrl")
                    : t(link.kind === "vpn" ? "settingsPage.paths.vpnAddress" : "settingsPage.paths.localIp", { name: link.interface })}
                  {/* État RÉEL du répondeur mDNS (backend utils/mdns.py::get_status) : « failed »/« unavailable »
                      signifie que seules les adresses IP ci-dessus sont fiables pour le moment. */}
                  {link.kind === "mdns" && (data.network.mdns_status === "failed" || data.network.mdns_status === "unavailable") && (
                    <span title={t("settingsPage.paths.mdnsUnavailableHint")} style={{ display: "inline-flex", color: "var(--accent-warning, #c77700)" }}>
                      <Icon name="warning" size={14} />
                    </span>
                  )}
                </div>
                <AddressList
                  base={link.url}
                  pages={data.deployment_profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS}
                  t={t}
                  onCopy={handleCopyPath}
                  copyLabel={t("settingsPage.paths.copyPath")}
                />
              </div>
            ))}
          {data.network.port80_redirect === false && (
            <p className="settings-hint" style={{ margin: "8px 0 0" }}>{t("settingsPage.paths.portRequiredHint", { port: String(data.network.port) })}</p>
          )}
        </details>

        {/* 3. Données et Chemins système */}
        <details className="settings-doc-group" open={!isMobile}>
          <summary className="settings-doc-header">
            <Icon name="folder" size={18} />
            <span>{t("settingsPage.paths.systemHeading")}</span>
          </summary>
          <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.systemHint")}</p>

          <div style={{ margin: "8px 0 14px", padding: "10px 14px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--accent-primary) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--accent-primary) 28%, transparent)", display: "flex", alignItems: "center", gap: "10px" }}>
            <Icon name="smartphone" size={18} color="var(--accent-text)" />
            <span style={{ fontSize: "0.85rem", lineHeight: 1.45, color: "var(--text-main)" }}>
              {t("settingsPage.paths.androidStorageNote")}
            </span>
          </div>

          <div className="settings-paths">
            {Object.entries(data.paths).map(([key, value]) => {
              const cleanPath = value.replace(/^sqlite:\/\/\//, "");
              return (
                <div key={key} className="settings-path-row settings-path-row--system">
                  <span className="settings-path-key">{t(PATH_LABEL_KEYS[key] || key)}</span>
                  <span className="settings-path-val settings-path-val--path" title={value}>
                    {value}
                  </span>
                  <div className="settings-path-actions">
                    <button
                      type="button"
                      className="btn btn-secondary olc-press"
                      style={{ height: "30px", padding: "0 10px", fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "4px" }}
                      onClick={() => handleCopyPath(cleanPath)}
                      title={t("settingsPage.paths.copyPath")}
                    >
                      <Icon name="content_copy" size={14} />
                      <span>{t("settingsPage.paths.copyPath")}</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary olc-press"
                      style={{ height: "30px", padding: "0 10px", fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "4px" }}
                      onClick={() => handleOpenPath(cleanPath)}
                      title={t("settingsPage.paths.openFolder")}
                    >
                      <Icon name="folder_open" size={14} />
                      <span>{t("settingsPage.paths.openFolder")}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </details>
      </section>

      {/* ---- Zone de danger : réinitialisation usine & désinstallation ---- */}
      <section className="live-block settings-danger" id="section-danger" hidden={!shows("section-danger")}>
        <h3 style={{ margin: "0 0 6px 0" }}>
          <Icon name="warning" size={18} /> {t("settingsPage.dangerSection")}
        </h3>
        <p className="settings-hint" style={{ margin: "0 0 16px 0" }}>
          {t("settingsPage.dangerHint")}
        </p>

        <div className="settings-danger-group">
          {/* 1. Remise à zéro des données (universelle tous profils) */}
          <div className="settings-danger-card">
            <h4>
              <Icon name="cleaning_services" size={18} /> {t("settingsPage.resetDataTitle")}
            </h4>
            <p>{t("settingsPage.resetDataHint")}</p>
            <div>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => setShowResetData(true)}
              >
                <Icon name="cleaning_services" size={16} /> {t("settingsPage.resetDataAction")}
              </button>
            </div>
          </div>

          {/* 2. Désinstallation du logiciel (tous profils avec bouton automatique) */}
          <div className="settings-danger-card">
            <h4>
              <Icon name="delete_forever" size={18} /> {t("settingsPage.uninstallSectionTitle")}
            </h4>
            <p>
              {t(
                data.deployment_profile === "windows"
                  ? "settingsPage.uninstallDesktopWindows"
                  : data.deployment_profile === "macos"
                  ? "settingsPage.uninstallDesktopMacos"
                  : data.deployment_profile === "android"
                  ? "settingsPage.uninstallDesktopAndroid"
                  : data.deployment_profile === "linux-headless"
                  ? "settingsPage.uninstallHint"
                  : "settingsPage.uninstallDesktopLinux",
              )}
            </p>
            <div>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => setShowUninstall(true)}
              >
                <Icon name="delete_forever" size={16} /> {t("settingsPage.uninstallAction")}
              </button>
            </div>
            <div className="settings-danger-manual">
              {t(
                data.deployment_profile === "windows"
                  ? "settingsPage.uninstallManualHintWindows"
                  : data.deployment_profile === "macos"
                  ? "settingsPage.uninstallManualHintMacos"
                  : data.deployment_profile === "android"
                  ? "settingsPage.uninstallManualHintAndroid"
                  : data.deployment_profile === "linux-headless"
                  ? "settingsPage.uninstallManualHintHeadless"
                  : "settingsPage.uninstallManualHintLinux",
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ---- Modale : resync ---- */}
      {showResetConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>{t("settingsPage.syncResetButton")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{t("settingsPage.syncResetConfirm")}</p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowResetConfirm(false)} disabled={resetting}>{t("common.cancel")}</button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={handleFullReset} disabled={resetting}>
                {resetting ? t("settingsPage.syncResetInProgress") : t("settingsPage.syncResetButton")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Modale : confirmation du passage au canal Bêta ou Canary ---- */}
      {confirmingChannel && (
        <div className="modal-overlay">
          <div className="modal-content">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={channelLogoUrl(confirmingChannel)}
              alt=""
              width={72}
              height={72}
              style={{ display: "block", margin: "0 auto", borderRadius: "var(--radius-md)" }}
            />
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)", textAlign: "center" }}>
              {t("settingsPage.updateChannelConfirmTitle", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(confirmingChannel)}`) })}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t(`settingsPage.updateChannelConfirmWarning${channelI18nSuffix(confirmingChannel)}`)}
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setConfirmingChannel(null)} disabled={changingChannel}>{t("common.cancel")}</button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={changingChannel}
                onClick={() => { const channel = confirmingChannel; setConfirmingChannel(null); handleChannelChange(channel); }}
              >
                {t("settingsPage.updateChannelConfirmButton", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(confirmingChannel)}`) })}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Modale : désinstallation (recopie de phrase obligatoire) ---- */}
      {showUninstall && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-error-text)" }}>
              <Icon name="delete_forever" size={20} /> {t("settingsPage.uninstallButton")}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{t("settingsPage.uninstallConfirmText")}</p>
            <ul className="settings-uninstall-list">
              <li>{t("settingsPage.uninstallItemServices")}</li>
              <li>{t("settingsPage.uninstallItemApp")}</li>
              <li>{t("settingsPage.uninstallItemData")}</li>
              <li>{t("settingsPage.uninstallItemKeepPackages")}</li>
            </ul>
            <label className="form-label" style={{ marginBottom: "4px" }}>
              {t("settingsPage.uninstallTypeLabel", { phrase: UNINSTALL_PHRASE })}
            </label>
            <input
              type="text"
              className="form-control"
              value={uninstallConfirm}
              onChange={(e) => setUninstallConfirm(e.target.value)}
              placeholder={UNINSTALL_PHRASE}
              autoFocus
            />
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => { setShowUninstall(false); setUninstallConfirm(""); }} disabled={uninstalling}>
                {t("common.cancel")}
              </button>
              <button type="button" className="btn btn-danger" onClick={handleUninstall} disabled={!uninstallReady || uninstalling}>
                {uninstalling ? t("settingsPage.uninstallInProgress") : t("settingsPage.uninstallConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Modale : restauration de sauvegarde ---- */}
      {showRestoreConfirm && selectedBackupFile && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-text)" }}>
              <Icon name="upload" size={20} /> {t("settingsPage.restoreBackup")}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("settingsPage.restoreBackupConfirmText")}
            </p>
            <div style={{ padding: "10px 14px", background: "var(--bg-surface-hover)", borderRadius: "8px", fontSize: "0.85rem", border: "1px solid var(--border-color)" }}>
              <strong>{t("settingsPage.restoreBackupPrompt")}</strong>
              <div style={{ marginTop: "4px", fontFamily: "var(--font-mono, monospace)" }}>
                {selectedBackupFile.name} ({formatBytes(selectedBackupFile.size)})
              </div>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => { setShowRestoreConfirm(false); setSelectedBackupFile(null); }}
                disabled={restoringBackup}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleRestoreBackup}
                disabled={restoringBackup}
              >
                {restoringBackup ? t("settingsPage.restoringBackup") : t("settingsPage.restoreBackup")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Modale : remise à zéro d'usine des données (recopie de phrase obligatoire) ---- */}
      {showResetData && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-error-text)" }}>
              <Icon name="cleaning_services" size={20} /> {t("settingsPage.resetDataButton")}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("settingsPage.resetDataConfirmText")}
            </p>
            <ul className="settings-uninstall-list">
              <li>{t("settingsPage.resetDataItemMedia")}</li>
              <li>{t("settingsPage.resetDataItemDb")}</li>
              <li>{t("settingsPage.resetDataItemKeepApp")}</li>
            </ul>
            <label className="form-label" style={{ marginBottom: "4px" }}>
              {t("settingsPage.resetDataTypeLabel", { phrase: RESET_DATA_PHRASE })}
            </label>
            <input
              type="text"
              className="form-control"
              value={resetDataConfirm}
              onChange={(e) => setResetDataConfirm(e.target.value)}
              placeholder={RESET_DATA_PHRASE}
              autoFocus
            />
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => { setShowResetData(false); setResetDataConfirm(""); }}
                disabled={resettingData}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleResetData}
                disabled={!resetDataReady || resettingData}
              >
                {resettingData ? t("settingsPage.resetDataInProgress") : t("settingsPage.resetDataConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
