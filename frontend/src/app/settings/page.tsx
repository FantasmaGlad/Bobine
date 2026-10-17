"use client";

import React, { useEffect, useState, useCallback } from "react";
import BrowserCompatibility from "@/components/BrowserCompatibility";
import { useAppSettings, type Theme } from "@/lib/AppSettingsContext";
import type { Language } from "@/lib/i18n";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";
import MarkdownView from "@/components/MarkdownView";
import AddressList from "@/components/AddressList";
import StartOnBootToggle from "@/components/StartOnBootToggle";
import { useIsMobile } from "@/lib/useIsMobile";

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
  wait_time_between_courses: number;
  volume_default: number;
  audio_chain_timer_seconds: number;
  radio_announcement_fade_ms: number;
  logs_retention_days?: number;
  deployment_profile: DeploymentProfile;
  paths: Record<string, string>;
  network: { local_ip: string | null; port: number; mdns_url: string; mdns_status: string | null };
  update_channel: "stable" | "beta" | "canary";
  wired_display_mode: "dual_screen" | "headless";
  auto_update_enabled: "true" | "false";
  auto_update_time: string;
}


interface UpdateInfo {
  online: boolean;
  channel?: "stable" | "beta" | "canary";
  current_version: string;
  current_tag: string;
  current_commit: string;
  latest_version: string | null;
  has_update: boolean;
  /** Vrai quand la version proposée est ANTÉRIEURE à celle installée
   * (retour Bêta/Canary -> Stable demandé explicitement via le sélecteur de canal). */
  is_downgrade?: boolean;
  error_code?: "offline" | "rate_limited" | "not_found_beta" | "not_found_canary" | "not_found_stable" | null;
  local_build?: "stable" | "beta" | "canary";
  release_title: string | null;
  release_notes: string | null;
  published_at: string | null;
  html_url: string | null;
  can_auto_apply?: boolean;
  /** Application installée depuis une boutique (Google Play) : les mises à jour passent par elle. */
  store_managed?: boolean;
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

interface ThemeSwatch {
  value: Theme;
  labelKey: string;
  category: "clair" | "sombre";
  colors: [string, string, string, string];
}

const THEME_SWATCHES: ThemeSwatch[] = [
  // --- Thèmes clairs ---
  { value: "clair", labelKey: "settingsPage.themeLight", category: "clair", colors: ["#f6f7f9", "#ffffff", "#e11d48", "#0f172a"] },
  { value: "charbon", labelKey: "settingsPage.themeCharbon", category: "clair", colors: ["#f4f4f5", "#e4e4e7", "#18181b", "#09090b"] },
  { value: "miel", labelKey: "settingsPage.themeMiel", category: "clair", colors: ["#faf8f5", "#ffffff", "#d97706", "#18130c"] },
  { value: "menthe", labelKey: "settingsPage.themeMenthe", category: "clair", colors: ["#f4f8f6", "#ffffff", "#059669", "#0c1d15"] },
  { value: "ciel", labelKey: "settingsPage.themeCiel", category: "clair", colors: ["#f4f7fb", "#ffffff", "#0071e3", "#0b1929"] },
  { value: "lavande", labelKey: "settingsPage.themeLavande", category: "clair", colors: ["#f7f6fb", "#ffffff", "#7c3aed", "#161126"] },
  { value: "beige", labelKey: "settingsPage.themeBeige", category: "clair", colors: ["#f7f5f0", "#ffffff", "#9a5b25", "#1c1814"] },
  { value: "coco", labelKey: "settingsPage.themeCoco", category: "clair", colors: ["#f8f5f2", "#ffffff", "#7c3a19", "#1f1510"] },

  // --- Thèmes sombres ---
  { value: "les-mills-sombre", labelKey: "settingsPage.themeDark", category: "sombre", colors: ["#08090b", "#191c22", "#e4002b", "#f8fafc"] },
  { value: "charbon-sombre", labelKey: "settingsPage.themeCharbonSombre", category: "sombre", colors: ["#0a0c10", "#1a202a", "#e2e8f0", "#f1f5f9"] },
  { value: "automne", labelKey: "settingsPage.themeAutomne", category: "sombre", colors: ["#0b0908", "#201b16", "#f97316", "#faf8f5"] },
  { value: "hiver", labelKey: "settingsPage.themeHiver", category: "sombre", colors: ["#070b0f", "#15202b", "#06b6d4", "#f4f9fc"] },
  { value: "lune", labelKey: "settingsPage.themeLune", category: "sombre", colors: ["#080911", "#181c30", "#6366f1", "#f6f7fe"] },
  { value: "chili", labelKey: "settingsPage.themeChili", category: "sombre", colors: ["#0b0809", "#20171a", "#f43f5e", "#fcf7f8"] },
  { value: "orchidee", labelKey: "settingsPage.themeOrchidee", category: "sombre", colors: ["#09080d", "#1b1726", "#d946ef", "#faf7fc"] },
  { value: "taupe", labelKey: "settingsPage.themeTaupe", category: "sombre", colors: ["#0b0a09", "#201d19", "#eab308", "#fafaf9"] },
];

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
  { path: "/radio", labelKey: "settingsPage.paths.pageRadio" },
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
    theme, language, setTheme, setLanguage, t,
    hasCustomLogo, activeLogo, setActiveLogo, refreshBranding,
    wiredDisplayMode, displayModeSetting, setDisplayModeSetting, displayExternalCount,
  } = useAppSettings();
  const isMobile = useIsMobile();
  const [data, setData] = useState<SettingsData | null>(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [loading, setLoading] = useState(true);

  const [refreshingNetwork, setRefreshingNetwork] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [confirmingChannel, setConfirmingChannel] = useState<"beta" | "canary" | null>(null);
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
              const el = document.getElementById("updates-section");
              if (el) el.scrollIntoView({ behavior: "smooth" });
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

  const handleAutoUpdateChange = async (patch: { auto_update_enabled?: "true" | "false"; auto_update_time?: string }) => {
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
  const handleChannelChange = async (channel: "stable" | "beta" | "canary") => {
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
        showToast(t(channel === "stable" ? "settingsPage.updateChannelLeft" : "settingsPage.updateChannelJoined", { channel: t(`settingsPage.updateChannel${channel === "beta" ? "Beta" : "Canary"}`) }));
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
        showToast("Rétention des logs enregistrée", "success");
      } else {
        showToast(t("settingsPage.saveError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const handlePurgeLogs = async () => {
    if (!window.confirm("Purger définitivement les journaux et historiques de métriques plus anciens que la période configurée ?")) return;
    setIsPurgingLogs(true);
    try {
      const res = await fetch(getApiUrl("/settings/logs/purge"), { method: "POST" });
      const body = await res.json();
      if (res.ok) {
        const details = body.details;
        const msg = details
          ? `Nettoyage terminé : ${details.purged_logs} logs et ${details.purged_metrics} métriques supprimés.`
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
    try {
      await navigator.clipboard.writeText(p);
      showToast(t("settingsPage.paths.pathCopied"));
    } catch {
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
          await navigator.clipboard.writeText(p).catch(() => {});
          showToast(resData.message || t("settingsPage.paths.pathCopied"));
        } else {
          showToast(t("settingsPage.paths.folderOpened"));
        }
      } else {
        showToast(resData.detail || "Impossible d'ouvrir le dossier", "error");
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

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

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
          {toast.type === "warning" && <Icon name="system_update" size={18} color="var(--accent-primary)" />}
          <span>{toast.message}</span>
          {toast.onClick && <Icon name="arrow_downward" size={16} />}
        </div>
      )}

      <div className="settings-nav-tabs sticky-glass-toolbar">
        <a href="#section-appearance" className="settings-nav-tab" onClick={(e) => scrollToSection(e, "section-appearance")}>
          <Icon name="palette" size={16} />
          <span>{t("settingsPage.appearanceSection")}</span>
        </a>
        <a href="#section-display" className="settings-nav-tab" onClick={(e) => scrollToSection(e, "section-display")}>
          <Icon name="tv" size={16} />
          <span>{t("settingsPage.wiredDisplaySection")}</span>
        </a>
        <a href="#updates-section" className="settings-nav-tab" onClick={(e) => scrollToSection(e, "updates-section")}>
          <Icon name="system_update" size={16} />
          <span>{t("settingsPage.updatesSection")}</span>
        </a>
        <a href="#section-docs" className="settings-nav-tab" onClick={(e) => scrollToSection(e, "section-docs")}>
          <Icon name="description" size={16} />
          <span>{t("settingsPage.docSection")}</span>
        </a>
        <a href="#section-danger" className="settings-nav-tab danger" onClick={(e) => scrollToSection(e, "section-danger")}>
          <Icon name="warning" size={16} />
          <span>{t("settingsPage.dangerSection")}</span>
        </a>
      </div>

      {/* ---- Apparence : thèmes + langue ---- */}
      <section className="live-block" id="section-appearance">
        <h3><Icon name="palette" size={18} /> {t("settingsPage.appearanceSection")}</h3>
        <div className="form-group">
          <label className="form-label">{t("settingsPage.themeLabel")}</label>

          {/* Catégorie : Thèmes clairs */}
          <div style={{ marginTop: "10px", marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <Icon name="light_mode" size={16} />
            <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>
              {t("settingsPage.themeCategoryLight")}
            </span>
          </div>
          <div className="theme-picker-grid">
            {THEME_SWATCHES.filter((o) => o.category === "clair").map((option) => (
              <button
                key={option.value}
                type="button"
                className={`theme-picker-card ${theme === option.value ? "active" : ""}`}
                onClick={() => setTheme(option.value)}
              >
                <div className="theme-picker-swatch">
                  {option.colors.map((c, i) => (
                    <span key={i} style={{ background: c }} />
                  ))}
                </div>
                <span className="theme-picker-name">{t(option.labelKey)}</span>
              </button>
            ))}
          </div>

          {/* Catégorie : Thèmes sombres */}
          <div style={{ marginTop: "22px", marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <Icon name="dark_mode" size={16} />
            <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>
              {t("settingsPage.themeCategoryDark")}
            </span>
          </div>
          <div className="theme-picker-grid">
            {THEME_SWATCHES.filter((o) => o.category === "sombre").map((option) => (
              <button
                key={option.value}
                type="button"
                className={`theme-picker-card ${theme === option.value ? "active" : ""}`}
                onClick={() => setTheme(option.value)}
              >
                <div className="theme-picker-swatch">
                  {option.colors.map((c, i) => (
                    <span key={i} style={{ background: c }} />
                  ))}
                </div>
                <span className="theme-picker-name">{t(option.labelKey)}</span>
              </button>
            ))}
          </div>

          <p className="settings-hint">{t("settingsPage.themeHint")}</p>
        </div>

        <div className="form-group" style={{ maxWidth: "320px" }}>
          <label className="form-label">{t("settingsPage.languageLabel")}</label>
          <select className="form-control" value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
            <option value="fr">{t("settingsPage.languageFr")}</option>
            <option value="en">{t("settingsPage.languageEn")}</option>
          </select>
          <p className="settings-hint">{t("settingsPage.languageHint")}</p>
        </div>
      </section>

      {/* ---- Sortie câblée : Pupitre Studio (/grid) vs Headless (Écran physique & HDMI) ---- */}
      <section className="live-block" id="section-display">
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
                  <span style={{ color: "var(--accent-primary)", display: "flex", alignItems: "center" }}>
                    <Icon name="check_circle" size={18} />
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                {t("settingsPage.wiredDisplayModeAutoDesc")}
              </p>
              <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--accent-primary)", lineHeight: 1.4 }}>
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
                  <span style={{ color: "var(--accent-primary)", display: "flex", alignItems: "center" }}>
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
                  <span style={{ color: "var(--accent-primary)", display: "flex", alignItems: "center" }}>
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
            <div style={{ color: "var(--accent-primary)", marginTop: "1px", flexShrink: 0 }}>
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
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-primary)", fontWeight: 700, fontSize: "0.9rem", flexShrink: 0 }}>
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
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-primary)", fontWeight: 700, fontSize: "0.9rem", flexShrink: 0 }}>
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
      <section className="live-block">
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
                  style={{ height: "38px", color: "var(--accent-error)" }}
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
      <section className="live-block" id="updates-section">
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
              <button
                type="button"
                className={`btn btn-sm ${data.update_channel === "stable" ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: "6px" }}
                onClick={() => handleChannelChange("stable")}
                disabled={changingChannel}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo-stable.png" alt="" width={18} height={18} style={{ borderRadius: "4px" }} />
                {t("settingsPage.updateChannelStable")}
              </button>
              <button
                type="button"
                className={`btn btn-sm ${data.update_channel === "beta" ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: "6px" }}
                onClick={() => { if (data.update_channel !== "beta") setConfirmingChannel("beta"); }}
                disabled={changingChannel}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo-beta.png" alt="" width={18} height={18} style={{ borderRadius: "4px" }} />
                {t("settingsPage.updateChannelBeta")}
              </button>
              <button
                type="button"
                className={`btn btn-sm ${data.update_channel === "canary" ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: "6px" }}
                onClick={() => { if (data.update_channel !== "canary") setConfirmingChannel("canary"); }}
                disabled={changingChannel}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo-canary.png" alt="" width={18} height={18} style={{ borderRadius: "4px" }} />
                {t("settingsPage.updateChannelCanary")}
              </button>
            </div>
          </div>
          <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.updateChannelHint")}</p>

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

          {/* Résultat de la recherche */}
          {updateInfo?.store_managed && (
            <p className="settings-hint olc-anim-in" style={{ margin: 0 }}>{t("settingsPage.storeManagedHint")}</p>
          )}
          {updateInfo && !updateInfo.store_managed && (
            <div className="olc-anim-in" style={{ marginTop: "4px" }}>
              {updateInfo.has_update ? (
                <div
                  className="update-card-banner"
                  style={{
                    borderLeft: "4px solid var(--accent-primary)",
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
                    borderLeft: "4px solid var(--accent-primary)",
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
      <BrowserCompatibility />

      {/* ---- Sauvegarde & Restauration universelle ---- */}
      <section className="live-block">
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
      <section className="live-block">
        <h3><Icon name="sync" size={18} /> {t("settingsPage.syncSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.syncHint")}</p>
        <button type="button" className="btn btn-secondary" style={{ height: "44px", alignSelf: "flex-start" }} onClick={() => setShowResetConfirm(true)}>
          <Icon name="sync" size={16} /> {t("settingsPage.syncResetButton")}
        </button>
      </section>

      {/* ---- Maintenance : Nettoyage des journaux & métriques ---- */}
      <section className="live-block">
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

      <StartOnBootToggle />

      {/* ---- Documentation : chemins (lecture seule) ---- */}
      <section className="live-block" id="section-docs">
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
          <div className="settings-paths">
            <div className="settings-path-row">
              <span className="settings-path-key">{t("settingsPage.paths.localIp")}</span>
              {data.network.local_ip ? (
                <a
                  href={`http://${data.network.local_ip}:${data.network.port}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="settings-path-link"
                >
                  {`http://${data.network.local_ip}:${data.network.port}`}
                </a>
              ) : (
                <span className="settings-path-val">{t("settingsPage.paths.localIpUnavailable")}</span>
              )}
            </div>
            <div className="settings-path-row">
              <span className="settings-path-key">{t("settingsPage.paths.mdnsUrl")}</span>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <a
                  href={data.network.mdns_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="settings-path-link"
                >
                  {data.network.mdns_url}
                </a>
                {/* Reflète l'état RÉEL du répondeur mDNS (cf. backend
                    utils/mdns.py::get_status) plutôt que d'afficher cette
                    URL comme si elle fonctionnait toujours — "failed"/
                    "unavailable" signifie que la découverte par IP directe
                    ci-dessus reste le seul moyen fiable pour le moment. */}
                {(data.network.mdns_status === "failed" || data.network.mdns_status === "unavailable") && (
                  <span
                    title={t("settingsPage.paths.mdnsUnavailableHint")}
                    style={{ display: "inline-flex", alignItems: "center", color: "var(--accent-warning, #c77700)" }}
                  >
                    <Icon name="warning" size={14} />
                  </span>
                )}
              </div>
            </div>
          </div>
          {data.network.local_ip && (
            <AddressList
              base={`http://${data.network.local_ip}:${data.network.port}`}
              pages={data.deployment_profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS}
              t={t}
              onCopy={handleCopyPath}
              copyLabel={t("settingsPage.paths.copyPath")}
              showHost={false}
            />
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
            <Icon name="smartphone" size={18} color="var(--accent-primary)" />
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
      <section className="live-block settings-danger" id="section-danger">
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
                className="btn btn-secondary"
                style={{ height: "42px", color: "var(--accent-error)", borderColor: "var(--accent-error)" }}
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
                style={{ height: "42px" }}
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
              src={`/logo-${confirmingChannel}.png`}
              alt=""
              width={72}
              height={72}
              style={{ display: "block", margin: "0 auto", borderRadius: "var(--radius-md)" }}
            />
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)", textAlign: "center" }}>
              {t("settingsPage.updateChannelConfirmTitle", { channel: t(`settingsPage.updateChannel${confirmingChannel === "beta" ? "Beta" : "Canary"}`) })}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t(`settingsPage.updateChannelConfirmWarning${confirmingChannel === "beta" ? "Beta" : "Canary"}`)}
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setConfirmingChannel(null)} disabled={changingChannel}>{t("common.cancel")}</button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={changingChannel}
                onClick={() => { const channel = confirmingChannel; setConfirmingChannel(null); handleChannelChange(channel); }}
              >
                {t("settingsPage.updateChannelConfirmButton", { channel: t(`settingsPage.updateChannel${confirmingChannel === "beta" ? "Beta" : "Canary"}`) })}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Modale : désinstallation (recopie de phrase obligatoire) ---- */}
      {showUninstall && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-error)" }}>
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
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-primary)" }}>
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
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-error)" }}>
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
