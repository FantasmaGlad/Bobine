"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useAppSettings, type Theme } from "@/lib/AppSettingsContext";
import type { Language } from "@/lib/i18n";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";

// Profil de déploiement (réf. PortabiliteCrossPlatformX §5.1) — détermine si
// la zone Désinstaller propose une action directe (appliance headless) ou de
// simples instructions (profils desktop, cf. section "Zone de danger" plus
// bas).
type DeploymentProfile = "linux-headless" | "linux-desktop" | "windows" | "macos";

interface SettingsData {
  wait_time_between_courses: number;
  volume_default: number;
  audio_chain_timer_seconds: number;
  radio_announcement_fade_ms: number;
  deployment_profile: DeploymentProfile;
  paths: Record<string, string>;
  network: { local_ip: string | null; port: number; mdns_url: string };
  update_channel: "stable" | "beta";
}

interface StorageData {
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  used_percent: number;
  app_bytes: number;
  path: string;
}

interface SystemUsageData {
  cpu_percent: number;
  memory_total_bytes: number;
  memory_used_bytes: number;
  memory_percent: number;
}

interface UpdateInfo {
  online: boolean;
  channel?: "stable" | "beta";
  current_version: string;
  current_tag: string;
  current_commit: string;
  latest_version: string | null;
  has_update: boolean;
  release_title: string | null;
  release_notes: string | null;
  published_at: string | null;
  html_url: string | null;
  can_auto_apply?: boolean;
  download_url?: string | null;
  asset_name?: string | null;
  asset_size?: number | null;
  deployment_profile?: DeploymentProfile;
  message?: string;
  checked_at: string;
}

/** Jauge circulaire (réf. mission "supervision cpu/ram en plus du stockage,
 * via des camemberts") : même technique conic-gradient déjà utilisée pour
 * l'anneau de progression "à suivre" de l'écran cinéma (cinema/page.tsx) —
 * aucune dépendance de graphique supplémentaire. */
function UsageGauge({ label, percent, detail, size = 96 }: { label: string; percent: number; detail: string; size?: number }) {
  const clamped = Math.max(0, Math.min(100, percent));
  const color = clamped >= 90 ? "var(--accent-error)" : clamped >= 75 ? "#f59e0b" : "var(--accent-primary)";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", flex: "1 1 140px", minWidth: "140px" }}>
      <div
        style={{
          position: "relative", width: size, height: size, borderRadius: "50%",
          background: `conic-gradient(${color} ${clamped * 3.6}deg, var(--bg-surface-hover) 0deg)`,
          display: "flex", alignItems: "center", justifyContent: "center",
          transition: "background 0.6s ease",
        }}
      >
        <div style={{
          width: size - 18, height: size - 18, borderRadius: "50%", background: "var(--bg-surface)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <span style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-main)", fontVariantNumeric: "tabular-nums" }}>
            {clamped.toFixed(0)}%
          </span>
        </div>
      </div>
      <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-main)" }}>{label}</span>
      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textAlign: "center" }}>{detail}</span>
    </div>
  );
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
  { value: "clair", labelKey: "settingsPage.themeLight", category: "clair", colors: ["#f8f9fa", "#ffffff", "#e4002b", "#16161a"] },
  { value: "charbon", labelKey: "settingsPage.themeCharbon", category: "clair", colors: ["#f4f4f5", "#ffffff", "#18181b", "#09090b"] },
  { value: "miel", labelKey: "settingsPage.themeMiel", category: "clair", colors: ["#fdfbf5", "#fef7e7", "#d97706", "#2d1e0b"] },
  { value: "coco", labelKey: "settingsPage.themeCoco", category: "clair", colors: ["#faf7f4", "#f3ece6", "#78350f", "#2c1d14"] },
  { value: "menthe", labelKey: "settingsPage.themeMenthe", category: "clair", colors: ["#f4f9f6", "#eaf3ee", "#10b981", "#132a1e"] },
  { value: "ciel", labelKey: "settingsPage.themeCiel", category: "clair", colors: ["#f0f7fa", "#e2eff5", "#0284c7", "#0c2738"] },
  { value: "beige", labelKey: "settingsPage.themeBeige", category: "clair", colors: ["#f7f4ec", "#ede7d8", "#453229", "#241a15"] },
  { value: "lavande", labelKey: "settingsPage.themeLavande", category: "clair", colors: ["#f7f6fc", "#edeaf7", "#7c3aed", "#1e1633"] },

  // --- Thèmes sombres ---
  { value: "les-mills-sombre", labelKey: "settingsPage.themeDark", category: "sombre", colors: ["#0a0a0a", "#1e1e20", "#e4002b", "#ffffff"] },
  { value: "lune", labelKey: "settingsPage.themeLune", category: "sombre", colors: ["#0d111a", "#1e2638", "#6366f1", "#f1f5f9"] },
  { value: "automne", labelKey: "settingsPage.themeAutomne", category: "sombre", colors: ["#14100c", "#282119", "#f59e0b", "#fef3c7"] },
  { value: "hiver", labelKey: "settingsPage.themeHiver", category: "sombre", colors: ["#0a1317", "#182830", "#06b6d4", "#f0fdfa"] },
  { value: "chili", labelKey: "settingsPage.themeChili", category: "sombre", colors: ["#15090a", "#2b1417", "#ef4444", "#fdf2f2"] },
  { value: "orchidee", labelKey: "settingsPage.themeOrchidee", category: "sombre", colors: ["#140d17", "#281b30", "#a855f7", "#faf5ff"] },
  { value: "taupe", labelKey: "settingsPage.themeTaupe", category: "sombre", colors: ["#1c1713", "#332a23", "#d4a373", "#fdfaf7"] },
];

// Pages plein écran destinées à être ouvertes depuis un AUTRE appareil du
// réseau local (TV câblée, tablette coach, poste radio dédié…), réf. mission
// "documenter les urls avec l'ip dynamique par page" — même liste que
// `isFullscreenRoute` dans ClientLayout.tsx.
const PUBLIC_PAGE_KEYS: { path: string; labelKey: string }[] = [
  { path: "/kiosk", labelKey: "settingsPage.paths.pageKiosk" },
  { path: "/cinema", labelKey: "settingsPage.paths.pageCinema" },
  { path: "/coach", labelKey: "settingsPage.paths.pageCoach" },
  { path: "/radio", labelKey: "settingsPage.paths.pageRadio" },
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
};

// Phrase à recopier pour armer la désinstallation (comparée sans casse/accent).
const UNINSTALL_PHRASE = "DÉSINSTALLER";
const RESET_DATA_PHRASE = "RÉINITIALISER";
const normalizePhrase = (s: string) => s.trim().toUpperCase().replace(/É/g, "E");

export default function SettingsPage() {
  const {
    theme, language, setTheme, setLanguage, t,
    hasCustomLogo, activeLogo, setActiveLogo, launchAnimationEnabled, setLaunchAnimationEnabled, refreshBranding,
  } = useAppSettings();
  const [data, setData] = useState<SettingsData | null>(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [storage, setStorage] = useState<StorageData | null>(null);
  const [system, setSystem] = useState<SystemUsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingNetwork, setRefreshingNetwork] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
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

  const showToast = (message: string, type: ToastState["type"] = "success") => setToast({ message, type });

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  const fetchSettings = useCallback((showIndicator = false) => {
    if (showIndicator) setRefreshingNetwork(true);
    return fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (d) setData(d);
      })
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        if (showIndicator) setRefreshingNetwork(false);
      });
  }, []);

  useEffect(() => {
    fetchSettings();
    const id = setInterval(() => fetchSettings(false), 15000);
    return () => clearInterval(id);
  }, [fetchSettings]);

  useEffect(() => {
    let cancelled = false;
    const fetchStorage = () => {
      fetch(getApiUrl("/settings/storage"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((d) => {
          if (!cancelled) setStorage(d);
        })
        .catch(() => {
          if (!cancelled) setStorage(null);
        });
    };
    fetchStorage();
    const id = setInterval(fetchStorage, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const fetchSystem = () => {
      fetch(getApiUrl("/settings/system"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((d) => {
          if (!cancelled) setSystem(d);
        })
        .catch(() => {
          if (!cancelled) setSystem(null);
        });
    };
    fetchSystem();
    // Intervalle plus court que le stockage (30s) : le CPU/RAM évoluent vite,
    // un affichage "en direct" a besoin d'un rafraîchissement fréquent.
    const id = setInterval(fetchSystem, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);


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

  // `silent` (réf. mission "notification de mise à jour disponible") : la
  // vérification automatique au montage de la page ne doit pas déranger
  // l'utilisateur avec un toast "Système à jour" à chaque ouverture des
  // Réglages — seule une mise à jour RÉELLEMENT disponible mérite un toast
  // non sollicité. Le clic manuel sur "Rechercher une mise à jour" garde
  // lui son retour complet (y compris "à jour"/erreur), pour confirmer que
  // le clic a bien fait quelque chose.
  const checkForUpdates = async (silent = false) => {
    setCheckingUpdate(true);
    try {
      const res = await fetch(getApiUrl("/updates/check"), { cache: "no-store" });
      if (res.ok) {
        const info: UpdateInfo = await res.json();
        setUpdateInfo(info);
        if (info.has_update) {
          showToast(t("settingsPage.updateAvailable"), "warning");
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

  // Notification proactive (réf. mission "notification de mise à jour
  // disponible") : vérifie une fois à l'ouverture des Réglages, sans
  // attendre un clic manuel sur "Rechercher une mise à jour" — silencieux
  // sauf si une mise à jour est réellement trouvée (cf. paramètre `silent`
  // ci-dessus).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- vérification ponctuelle contre une API externe (GitHub via le backend), pas un calcul dérivable au rendu
    checkForUpdates(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule vérification au montage, volontairement indépendante des re-rendus de checkForUpdates
  }, []);

  const handleApplyUpdate = async () => {
    if (!window.confirm(t("settingsPage.applyUpdate") + " ?")) return;
    setApplyingUpdate(true);
    try {
      const res = await fetch(getApiUrl("/updates/apply"), { method: "POST" });
      if (res.ok) {
        showToast(t("settingsPage.updateSuccess"), "success");
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

  // Programme Bobine Beta (réf. mission "canal Stable/Bêta") : bascule
  // immédiate (comme le thème/la langue), pas de bouton "Enregistrer" séparé
  // — c'est un choix binaire sans état intermédiaire à valider. Relance
  // aussitôt checkForUpdates() pour que la carte "Mises à jour" reflète tout
  // de suite le nouveau canal plutôt que de garder l'ancien résultat affiché
  // jusqu'au prochain clic manuel sur "Rechercher une mise à jour".
  const handleChannelChange = async (channel: "stable" | "beta") => {
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
        showToast(t(channel === "beta" ? "settingsPage.betaJoined" : "settingsPage.betaLeft"));
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
        <div className={`toast ${toast.type}`}>
          <span>{toast.message}</span>
        </div>
      )}

      <div className="settings-head">
        <h1 className="settings-title">{t("header.settingsTitle")}</h1>
        <p className="settings-subtitle">{t("settingsPage.subtitle")}</p>
      </div>

      {/* ---- Apparence : thèmes + langue ---- */}
      <section className="live-block">
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

      {/* ---- Animation de lancement (vidéo d'intro câblée) ---- */}
      <section className="live-block">
        <h3><Icon name="movie" size={18} /> {t("settingsPage.launchAnimationSection")}</h3>
        <div className="form-group" style={{ flexDirection: "column", gap: "8px", alignItems: "flex-start" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
            <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
              {t("settingsPage.launchAnimationLabel")}
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
                className={`btn btn-sm ${launchAnimationEnabled ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                onClick={() => setLaunchAnimationEnabled(true)}
              >
                {t("common.yes")}
              </button>
              <button
                type="button"
                className={`btn btn-sm ${!launchAnimationEnabled ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                onClick={() => setLaunchAnimationEnabled(false)}
              >
                {t("common.no")}
              </button>
            </div>
          </div>
          <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.launchAnimationHint")}</p>
        </div>
      </section>

      {/* ---- Supervision (stockage, CPU, RAM) ---- */}
      <section className="live-block">
        <h3><Icon name="monitor_heart" size={18} /> {t("settingsPage.monitoringSection")}</h3>
        {storage || system ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "20px", justifyContent: "space-around" }}>
              {storage && (
                <UsageGauge
                  label={t("settingsPage.storageSection")}
                  percent={storage.used_percent}
                  detail={t("settingsPage.storageFreeOfTotal", { free: formatBytes(storage.free_bytes), total: formatBytes(storage.total_bytes) })}
                />
              )}
              {system && (
                <UsageGauge label={t("settingsPage.cpuLabel")} percent={system.cpu_percent} detail={t("settingsPage.cpuHint")} />
              )}
              {system && (
                <UsageGauge
                  label={t("settingsPage.ramLabel")}
                  percent={system.memory_percent}
                  detail={t("settingsPage.ramDetail", { used: formatBytes(system.memory_used_bytes), total: formatBytes(system.memory_total_bytes) })}
                />
              )}
            </div>
            {storage && (
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{t("settingsPage.storageApp", { app: formatBytes(storage.app_bytes) })}</span>
            )}
            <p className="settings-hint">{t("settingsPage.storageHint")}</p>
          </div>
        ) : (
          <p className="live-empty">{t("settingsPage.storageError")}</p>
        )}
      </section>

      {/* ---- Mises à jour logicielles ---- */}
      <section className="live-block">
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
              <strong>{updateInfo?.current_version ?? "V3.0.2"}</strong>
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

          {/* Programme Bobine Beta (réf. mission "canal Stable/Bêta") */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
            <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
              {t("settingsPage.betaLabel")}
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
                className={`btn btn-sm ${data.update_channel !== "beta" ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                onClick={() => handleChannelChange("stable")}
                disabled={changingChannel}
              >
                {t("settingsPage.betaStable")}
              </button>
              <button
                type="button"
                className={`btn btn-sm ${data.update_channel === "beta" ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                onClick={() => handleChannelChange("beta")}
                disabled={changingChannel}
              >
                {t("settingsPage.betaBeta")}
              </button>
            </div>
          </div>
          <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.betaHint")}</p>

          {/* Résultat de la recherche */}
          {updateInfo && (
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
                        {t("settingsPage.updateAvailable")}
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
                    {updateInfo.release_title || t("settingsPage.updateAvailableDetail")}
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
                          {updateInfo.release_notes}
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
                            {t("settingsPage.applyUpdate")}
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
                    <Icon name="wifi_off" size={16} />
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

      {/* ---- Zone de danger : réinitialisation usine & désinstallation ---- */}
      <section className="live-block settings-danger">
        <h3><Icon name="warning" size={18} /> {t("settingsPage.dangerSection")}</h3>

        {/* Remise à zéro des données (universelle tous profils) */}
        <div style={{ marginBottom: "20px" }}>
          <h4 style={{ margin: "0 0 6px 0", fontSize: "1rem", color: "var(--text-main)" }}>
            {t("settingsPage.resetDataButton")}
          </h4>
          <p className="settings-hint" style={{ marginTop: 0 }}>
            {t("settingsPage.resetDataHint")}
          </p>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ height: "44px", color: "var(--accent-error)", borderColor: "var(--accent-error)" }}
            onClick={() => setShowResetData(true)}
          >
            <Icon name="cleaning_services" size={16} /> {t("settingsPage.resetDataButton")}
          </button>
        </div>

        <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "16px" }}>
          <h4 style={{ margin: "0 0 6px 0", fontSize: "1rem", color: "var(--text-main)" }}>
            {t("settingsPage.uninstallButton")}
          </h4>
          {data.deployment_profile === "linux-headless" ? (
            <>
              <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.uninstallHint")}</p>
              <button type="button" className="btn btn-danger" style={{ height: "44px", alignSelf: "flex-start" }} onClick={() => setShowUninstall(true)}>
                <Icon name="delete_forever" size={16} /> {t("settingsPage.uninstallButton")}
              </button>
            </>
          ) : (
            <>
              <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.uninstallDesktopHint")}</p>
              <p className="settings-hint" style={{ marginTop: 0 }}>
                {t(
                  data.deployment_profile === "windows"
                    ? "settingsPage.uninstallDesktopWindows"
                    : data.deployment_profile === "macos"
                    ? "settingsPage.uninstallDesktopMacos"
                    : "settingsPage.uninstallDesktopLinux",
                )}
              </p>
            </>
          )}
        </div>
      </section>

      {/* ---- Documentation : chemins (lecture seule) ---- */}
      <section className="live-block">
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
        <div className="settings-paths">
          {/* IP locale (réf. mission "aide à la découverte réseau") : en
              complément du nom mDNS bobine.local (avahi, déjà annoncé en fin
              d'installation), utile quand la découverte par nom échoue (ex.
              client ne supportant pas mDNS). */}
          <div className="settings-path-row">
            <span className="settings-path-key">{t("settingsPage.paths.localIp")}</span>
            <span className="settings-path-val">
              {data.network.local_ip ? `http://${data.network.local_ip}:${data.network.port}` : t("settingsPage.paths.localIpUnavailable")}
            </span>
          </div>
          <div className="settings-path-row">
            <span className="settings-path-key">{t("settingsPage.paths.mdnsUrl")}</span>
            <span className="settings-path-val">{data.network.mdns_url}</span>
          </div>
          <div className="settings-path-row" style={{ marginTop: "10px" }}>
            <span className="settings-path-key" style={{ fontWeight: 800 }}>{t("settingsPage.paths.pagesHeading")}</span>
            <span />
          </div>
          {PUBLIC_PAGE_KEYS.map((page) => (
            <div key={page.path} className="settings-path-row">
              <span className="settings-path-key">{t(page.labelKey)}</span>
              <span className="settings-path-val">
                {data.network.local_ip
                  ? `http://${data.network.local_ip}:${data.network.port}${page.path}`
                  : t("settingsPage.paths.localIpUnavailable")}
              </span>
            </div>
          ))}
          {Object.entries(data.paths).map(([key, value]) => (
            <div key={key} className="settings-path-row">
              <span className="settings-path-key">{t(PATH_LABEL_KEYS[key] || key)}</span>
              <span className="settings-path-val">{value}</span>
            </div>
          ))}
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
