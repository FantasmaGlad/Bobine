"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { usePlaybackSocket, PlaybackState } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
import { navLinks, footerNavLinks } from "@/lib/navLinks";
import Icon from "@/components/Icon";

interface AudioCourseSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  track_count: number;
  total_duration_seconds: number;
}

interface AudioPlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
}

interface BackgroundSummary {
  id: number;
  title: string;
  is_image: boolean;
  thumbnail_path: string | null;
  duration_seconds: number | null;
}

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

function formatTime(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function CoachModePage() {
  const { t } = useAppSettings();
  const CHAIN_MODE_LABELS: Record<string, string> = {
    auto: t("coach.chainModeLabels.auto"),
    manual: t("coach.chainModeLabels.manual"),
  };
  // hasSynced (correctif "le bouton stop du mode coach ne marche pas") :
  // marque la réception du tout premier évènement websocket réel. Avant ce
  // correctif, `state` retombait sur `snapshotState` (pré-hydratation REST
  // figée au montage) dès que `wsState.current_audio_course` redevenait null
  // — ce qui est justement le cas normal après un Stop — donc l'écran
  // restait bloqué sur le cours coach obsolète au lieu de revenir au picker.
  const [hasSynced, setHasSynced] = useState(false);
  const { state: wsState, connected, sendCommand } = usePlaybackSocket(() => setHasSynced(true));
  const [courses, setCourses] = useState<AudioCourseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  // Playlists audio ("éditions mixées", réf. mission "création de playlists
  // spéciales juste avec les cours audios") : onglet séparé du picker de
  // cours isolés, plutôt qu'une longue liste mélangée.
  const [audioPlaylists, setAudioPlaylists] = useState<AudioPlaylistSummary[]>([]);
  const [pickerTab, setPickerTab] = useState<"courses" | "playlists">("courses");
  const [showTrackList, setShowTrackList] = useState(false);
  // Sélecteur de fond d'écran (réf. mission "afficher un fond, figé ou animé,
  // directement depuis le mode coach") : liste les fonds importés dans
  // l'admin, appliqués en direct sur l'écran câblé via audio_set_background.
  const [showBackgrounds, setShowBackgrounds] = useState(false);
  const [backgrounds, setBackgrounds] = useState<BackgroundSummary[]>([]);
  const [search, setSearch] = useState("");
  // Accès aux autres fonctions de l'admin sans quitter le mode coach (réf.
  // retour utilisateur "aucun bouton pour naviguer hors du mode coach sur le
  // téléphone") : ClientLayout masque sidebar/tiroir sur cette route en
  // plein écran, ce menu local est donc la seule porte de sortie vers les
  // autres pages — la navigation elle-même reste non destructive, le cours
  // coach continue de tourner côté serveur qu'on y revienne ou non.
  const [showNav, setShowNav] = useState(false);
  // État de snapshot HTTP (réf. Bug 4 / B4) : pré-hydrate l'interface avant
  // que le premier message WebSocket ne soit reçu. Sans cela, tous les boutons
  // de navigation de piste audio sont disabled car DEFAULT_STATE a
  // audio_tracks=null. Le WS prend le relais dès sa première notification.
  const [snapshotState, setSnapshotState] = useState<PlaybackState | null>(null);
  const state = hasSynced ? wsState : (snapshotState ?? wsState);

  useEffect(() => {
    fetch(getApiUrl("/playback/state"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: PlaybackState | null) => {
        if (data && data.state) setSnapshotState(data);
      })
      .catch(() => { /* échec silencieux, le WS prendra le relais */ });
  }, []);

  useEffect(() => {
    fetch(getApiUrl("/audio"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setCourses)
      .catch(() => setCourses([]))
      .finally(() => setLoading(false));

    fetch(getApiUrl("/backgrounds"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setBackgrounds)
      .catch(() => setBackgrounds([]));

    fetch(getApiUrl("/audio-playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setAudioPlaylists)
      .catch(() => setAudioPlaylists([]));
  }, []);

  const isCoachMode = state.state === "coach_mode";
  const course = state.current_audio_course;
  // Couleur du thème plutôt que du programme du cours (réf. correctif
  // "couleurs hardcodées associées à un cours" — le thème prime désormais).
  const accent = "var(--accent-primary)";
  const accentFg = useThemeAccentForeground();
  const tracks = state.audio_tracks || [];
  const trackIndex = state.audio_track_index ?? 0;
  const currentTrack = tracks[trackIndex] || null;

  const [localPos, setLocalPos] = useState<number>(0);

  useEffect(() => {
    setLocalPos(state.audio_position_seconds || 0);
  }, [state.audio_position_seconds, state.audio_track_index]);

  useEffect(() => {
    if (!state.audio_playing) return;
    const timer = setInterval(() => {
      setLocalPos((prev) => {
        const dur = currentTrack?.duration_seconds;
        const next = prev + 0.1;
        if (dur && next > dur) return dur;
        return next;
      });
    }, 100);
    return () => clearInterval(timer);
  }, [state.audio_playing, currentTrack?.duration_seconds]);

  const remaining = currentTrack?.duration_seconds
    ? Math.max(0, currentTrack.duration_seconds - localPos)
    : null;
  const filteredCourses = courses.filter((c) => c.title.toLowerCase().includes(search.toLowerCase()));

  const filteredAudioPlaylists = audioPlaylists.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()));

  // Tap 2/2 : le choix du cours suffit à le lancer (réf. F10.4/UX4.9).
  const launchCourse = (courseId: number) => {
    sendCommand("load_audio_course", { audio_course_id: courseId });
  };

  // Idem pour une playlist audio ("édition mixée", réf. mission "playlists
  // spéciales... musiques de plusieurs RPM différents") : traitée côté
  // serveur comme un cours virtuel dont les pistes viennent de plusieurs
  // cours — même flux de lecture qu'un cours normal, pas de notion de
  // "cours suivant" à enchaîner.
  const launchAudioPlaylist = (playlistId: number) => {
    sendCommand("load_audio_playlist", { audio_playlist_id: playlistId });
  };

  const router = useRouter();

  const handleExitCoach = async () => {
    try {
      await sendCommand("stop");
    } finally {
      if (typeof window !== "undefined" && (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
        router.push("/grid");
      } else {
        router.push("/");
      }
    }
  };

  const handleBackFromPicker = () => {
    if (typeof window !== "undefined" && (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
      router.push("/grid");
    } else {
      router.push("/");
    }
  };

  const wasCoachModeRef = useRef(isCoachMode);
  useEffect(() => {
    if (wasCoachModeRef.current && !isCoachMode) {
      if (typeof window !== "undefined" && (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
        router.replace("/grid");
      }
    }
    wasCoachModeRef.current = isCoachMode;
  }, [isCoachMode, router]);

  const navSheet = showNav && (
    <div className="coach-sheet-overlay" onClick={() => setShowNav(false)}>
      <div className="coach-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="coach-sheet-handle" />
        <h3 style={{ margin: "0 0 12px" }}>{t("coach.otherFunctions")}</h3>
        <div className="coach-sheet-list">
          {[...navLinks, ...footerNavLinks].map((link) => (
            <Link key={link.href} href={link.href} className="nav-link" onClick={() => setShowNav(false)}>
              <Icon name={link.iconName} size={20} />
              <span>{t(link.labelKey)}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );

  if (!isCoachMode) {
    return (
      <div className="coach-screen coach-picker-screen">
        <div className="coach-picker-topbar">
          <button
            type="button"
            className="coach-icon-btn olc-press"
            onClick={handleBackFromPicker}
            title={t("coach.backToDashboard")}
          >
            <Icon name="arrow_back" size={20} />
          </button>
          <button className="coach-icon-btn olc-press" onClick={() => setShowNav(true)} title={t("coach.otherFunctions")}>
            <Icon name="menu" size={20} />
          </button>
        </div>
        <div className="coach-picker-header">
          <h1 className="coach-picker-title">{t("coach.title")}</h1>
          <p className="coach-picker-subtitle">
            {connected ? t("coach.chooseCourseHint") : t("coach.connectingHint")}
          </p>
          <input
            type="text"
            className="search-input coach-picker-search"
            placeholder={t("coach.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {/* Onglet Cours isolés / Playlists audio (réf. mission "éditions
              mixées") : deux listes distinctes plutôt qu'une seule mélangée. */}
          <div className="coach-picker-tabs">
            <button
              type="button"
              className={`speed-btn ${pickerTab === "courses" ? "active" : ""}`}
              onClick={() => setPickerTab("courses")}
            >
              {t("coach.coursesTab")}
            </button>
            <button
              type="button"
              className={`speed-btn ${pickerTab === "playlists" ? "active" : ""}`}
              onClick={() => setPickerTab("playlists")}
            >
              {t("coach.playlistsTab")}
            </button>
          </div>
        </div>
        <div className="coach-picker-list">
          {pickerTab === "courses" ? (
            loading ? (
              <p className="live-empty">{t("coach.loadingCourses")}</p>
            ) : filteredCourses.length === 0 ? (
              <p className="live-empty">{t("coach.noCoursesAvailable")}</p>
            ) : (
              filteredCourses.map((c, i) => (
                <button
                  key={c.id}
                  className="coach-course-item olc-press olc-card-hover olc-anim-in"
                  style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
                  onClick={() => launchCourse(c.id)}
                >
                  <span className="coach-course-item-accent" style={{ background: "var(--accent-primary)" }} />
                  <span className="coach-course-item-body">
                    <span className="coach-course-item-title">{c.title}</span>
                    <span className="coach-course-item-meta">
                      {c.program || t("coach.otherProgram")} · {t("coach.tracksCount", { count: c.track_count })}
                    </span>
                  </span>
                  <Icon name="play_circle" size={22} />
                </button>
              ))
            )
          ) : filteredAudioPlaylists.length === 0 ? (
            <p className="live-empty">{t("coach.noPlaylistsAvailable")}</p>
          ) : (
            filteredAudioPlaylists.map((p, i) => (
              <button
                key={p.id}
                className="coach-course-item olc-press olc-card-hover olc-anim-in"
                style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
                onClick={() => launchAudioPlaylist(p.id)}
              >
                <span className="coach-course-item-accent" style={{ background: "var(--accent-primary)" }} />
                <span className="coach-course-item-body">
                  <span className="coach-course-item-title">{p.name}</span>
                  <span className="coach-course-item-meta">
                    {t("coach.tracksInPlaylist", { count: p.item_count })}
                  </span>
                </span>
                <Icon name="play_circle" size={22} />
              </button>
            ))
          )}
        </div>
        {navSheet}
      </div>
    );
  }

  const activeBgId = state.current_background?.id ?? state.current_audio_course?.background_id ?? null;
  const activeBgTitle = state.current_background?.title ?? (
    activeBgId ? backgrounds.find((b) => b.id === activeBgId)?.title : null
  );
  const activeBgIsImage = state.current_background?.is_image ?? (
    activeBgId ? Boolean(backgrounds.find((b) => b.id === activeBgId)?.is_image) : false
  );
  const audioProgress = currentTrack?.duration_seconds && currentTrack.duration_seconds > 0
    ? Math.min(100, (localPos / currentTrack.duration_seconds) * 100)
    : 0;

  return (
    <div className="coach-screen coach-live-screen" style={{ borderTopColor: accent }}>
      {/* Barre supérieure universelle */}
      <div className="coach-live-header" style={{ maxWidth: "1280px", justifyContent: "flex-end" }}>
        <button className="coach-icon-btn olc-press" onClick={() => setShowNav(true)} title={t("coach.otherFunctions")}>
          <Icon name="menu" size={20} />
        </button>
      </div>

      {/* Grille responsive Console Régie (2 colonnes sur tablette/laptop, 1 colonne sur smartphone) */}
      <div className="coach-console-grid">
        {/* Colonne Gauche : Commandes audio centrées */}
        <div className="coach-audio-col">
          {/* Bloc Piste en cours */}
          <div className="coach-live-track-block olc-anim-in" key={currentTrack?.id} style={{ width: "100%", maxWidth: "420px" }}>
            <span className="coach-live-track-label">
              {currentTrack ? t("coach.trackLabel", { index: trackIndex + 1, total: tracks.length }) : t("coach.noTrack")}
            </span>
            <span className="coach-live-track-title">{currentTrack?.title}</span>
            <span className="coach-live-track-time">- {formatTime(remaining)}</span>
            <div style={{ width: "100%", height: "6px", background: "var(--bg-surface-elevated)", borderRadius: "3px", overflow: "hidden", marginTop: "10px" }}>
              <div style={{ width: `${audioProgress}%`, height: "100%", background: accent, transition: "width 0.25s linear" }} />
            </div>
          </div>

          {/* Commandes de lecture principales */}
          <div className="coach-controls-grid">
            <button className="coach-btn olc-press" onClick={() => sendCommand("audio_previous_track")} disabled={trackIndex <= 0} title="Précédent">
              <Icon name="skip_previous" size={28} filled />
            </button>
            <button
              className="coach-btn coach-btn-main olc-press"
              style={{ background: accent, color: accentFg }}
              onClick={() => sendCommand(state.audio_playing ? "pause" : "play")}
              title={state.audio_playing ? "Pause" : "Lecture"}
            >
              <Icon name={state.audio_playing ? "pause" : "play_arrow"} size={36} color={accentFg} filled />
            </button>
            <button
              className="coach-btn olc-press"
              onClick={() => sendCommand("audio_next_track")}
              disabled={trackIndex >= tracks.length - 1}
              title="Suivant"
            >
              <Icon name="skip_next" size={28} filled />
            </button>
          </div>

          <button className="coach-btn coach-btn-wide olc-press" onClick={() => sendCommand("audio_restart_track")}>
            <Icon name="restart_alt" size={18} />
            {t("coach.restartTrack")}
          </button>

          {/* Volume tactile */}
          <div className="coach-volume-row">
            <button className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.max(0, state.volume - 10) })}>
              <Icon name="remove" size={18} />
            </button>
            <span className="coach-volume-value">
              <Icon name="volume_up" size={16} style={{ marginRight: "4px" }} />
              {state.volume}%
            </span>
            <button className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.min(100, state.volume + 10) })}>
              <Icon name="add" size={18} />
            </button>
          </div>

          {/* Mode d'enchaînement */}
          <div className="coach-chain-mode-row">
            {(["auto", "manual"] as const).map((mode) => (
              <button
                key={mode}
                className={`speed-btn ${state.audio_chain_mode === mode ? "active" : ""}`}
                style={{ minHeight: "44px", flex: 1 }}
                onClick={() => sendCommand("audio_set_chain_mode", { mode })}
              >
                {CHAIN_MODE_LABELS[mode]}
              </button>
            ))}
          </div>

          {/* Bouton d'accès au tiroir déroulant des pistes */}
          <button
            type="button"
            className="coach-btn coach-btn-wide olc-press"
            style={{ minHeight: "52px", marginTop: "4px" }}
            onClick={() => setShowTrackList(true)}
          >
            <Icon name="queue_music" size={20} />
            <span>{t("coach.viewTracks", { count: tracks.length })}</span>
          </button>

          {/* Bouton Quitter le mode coach centré avec la structure */}
          <button
            type="button"
            className="coach-exit-btn-centered olc-press"
            onClick={handleExitCoach}
            title={t("coach.disableCoachMode")}
          >
            <Icon name="power_settings_new" size={20} />
            <span>Quitter le mode coach</span>
          </button>
        </div>

        {/* Colonne Droite : Retour Scène HDMI & Palette d'Ambiances */}
        <div className="coach-stage-col">
          {/* Moniteur Scène Grand Écran (Direct HDMI) */}
          <div className="coach-stage-monitor">
            {activeBgId ? (
              activeBgIsImage ? (
                <img
                  className="coach-monitor-media"
                  src={getApiUrl(`/backgrounds/${activeBgId}/stream`)}
                  alt=""
                />
              ) : (
                <video
                  className="coach-monitor-media"
                  src={getApiUrl(`/backgrounds/${activeBgId}/stream`)}
                  autoPlay
                  loop
                  muted
                  playsInline
                />
              )
            ) : (
              <div className="coach-monitor-placeholder">
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", opacity: 0.35 }}>
                  <Icon name="hide_image" size={36} color="var(--accent-primary)" />
                  <span style={{ fontSize: "0.8rem", fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    {t("coach.soberScreenActive")}
                  </span>
                </div>
              </div>
            )}

            <div className="coach-monitor-gradient" />

            <div className="coach-monitor-top">
              <span className="coach-monitor-badge">
                <span className="coach-monitor-live-dot" />
                {t("coach.stageMonitorTitle")}
              </span>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  padding: "3px 8px",
                  borderRadius: "12px",
                  background: "rgba(0, 0, 0, 0.6)",
                  color: "rgba(255, 255, 255, 0.9)",
                  backdropFilter: "blur(6px)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                }}
              >
                {activeBgTitle || t("coach.soberScreenActive")}
              </span>
            </div>

            <div className="coach-monitor-bottom">
              <h2 className="coach-monitor-track-title">
                {currentTrack?.title || course?.title}
              </h2>
              <div className="coach-monitor-meta">
                <span>{currentTrack ? t("coach.trackLabel", { index: trackIndex + 1, total: tracks.length }) : ""}</span>
                <span>
                  {formatTime(localPos)} / {formatTime(currentTrack?.duration_seconds)}
                </span>
              </div>
              <div style={{ width: "100%", height: "4px", background: "rgba(255, 255, 255, 0.2)", borderRadius: "2px", overflow: "hidden" }}>
                <div style={{ width: `${audioProgress}%`, height: "100%", background: accent, transition: "width 0.25s linear" }} />
              </div>
            </div>
          </div>

          {/* Palette Tactile d'Ambiances Visuelles */}
          <div className="coach-ambiance-panel">
            <div className="coach-ambiance-header">
              <div>
                <h3 style={{ fontSize: "1rem", fontWeight: 800, margin: 0 }}>
                  {t("coach.ambiancePaletteTitle")}
                </h3>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  {t("coach.stageMonitorHint")}
                </span>
              </div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>
                {t("coach.ambianceCount", { count: backgrounds.length })}
              </span>
            </div>

            {/* Bouton Écran Sobre */}
            <button
              type="button"
              className={`olc-press ${!activeBgId ? "active" : ""}`}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                width: "100%",
                minHeight: "40px",
                borderRadius: "var(--radius-md)",
                background: !activeBgId ? "color-mix(in srgb, var(--accent-primary) 15%, var(--bg-surface-elevated))" : "var(--bg-surface-elevated)",
                border: `1.5px solid ${!activeBgId ? "var(--accent-primary)" : "var(--border-color)"}`,
                color: !activeBgId ? "var(--accent-primary)" : "var(--text-main)",
                fontWeight: 700,
                fontSize: "0.82rem",
                cursor: "pointer",
              }}
              onClick={() => sendCommand("audio_set_background", { background_id: null })}
            >
              <Icon name="hide_image" size={18} />
              {t("coach.soberScreenBtn")}
              {!activeBgId && <Icon name="check_circle" size={16} filled />}
            </button>

            {/* Grille tactile d'ambiances 16:9 */}
            <div className="coach-ambiance-grid">
              {backgrounds.map((bg) => {
                const isActive = activeBgId === bg.id;
                const thumb = bg.thumbnail_path
                  ? getApiUrl(`/thumbnails/${bg.thumbnail_path.split("/").pop()}`)
                  : null;
                return (
                  <div
                    key={bg.id}
                    className={`coach-ambiance-thumb-card olc-press ${isActive ? "active" : ""}`}
                    onClick={() => sendCommand("audio_set_background", { background_id: bg.id })}
                    title={bg.title}
                  >
                    <div className="coach-ambiance-thumb-media">
                      {thumb ? (
                        <img src={thumb} alt={bg.title} />
                      ) : (
                        <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Icon name={bg.is_image ? "image" : "videocam"} size={22} style={{ opacity: 0.4 }} />
                        </div>
                      )}
                      {isActive && (
                        <span
                          style={{
                            position: "absolute",
                            top: 4,
                            right: 4,
                            background: "var(--accent-primary)",
                            color: "var(--accent-primary-fg)",
                            borderRadius: "4px",
                            padding: "1px 5px",
                            fontSize: "0.68rem",
                            fontWeight: 800,
                            boxShadow: "0 2px 6px rgba(0,0,0,0.5)",
                          }}
                        >
                          Actif
                        </span>
                      )}
                      <span
                        style={{
                          position: "absolute",
                          bottom: 3,
                          right: 3,
                          background: "rgba(0, 0, 0, 0.7)",
                          color: "#fff",
                          borderRadius: "3px",
                          padding: "1px 4px",
                          fontSize: "0.65rem",
                          fontWeight: 600,
                        }}
                      >
                        {bg.is_image ? "Image" : bg.duration_seconds ? `${Math.round(bg.duration_seconds)}s` : "Boucle"}
                      </span>
                    </div>
                    <div
                      style={{
                        padding: "6px 8px",
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: isActive ? "var(--accent-primary)" : "var(--text-main)",
                      }}
                    >
                      {bg.title}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom sheet Ambiances (sur smartphone) */}
      {showBackgrounds && (
        <div className="coach-sheet-overlay" onClick={() => setShowBackgrounds(false)}>
          <div className="coach-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="coach-sheet-handle" />
            <h3 style={{ margin: "0 0 12px" }}>{t("coach.backgroundsTitle")}</h3>
            <div className="coach-sheet-list">
              <button
                className={`coach-sheet-track olc-press ${!activeBgId ? "active" : ""}`}
                onClick={() => {
                  sendCommand("audio_set_background", { background_id: null });
                  setShowBackgrounds(false);
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Icon name="hide_image" size={18} />
                  {t("coach.noBackground")}
                </span>
                {!activeBgId && <Icon name="check_circle" size={18} color="var(--accent-primary)" filled />}
              </button>
              {backgrounds.map((bg) => (
                <button
                  key={bg.id}
                  className={`coach-sheet-track olc-press ${activeBgId === bg.id ? "active" : ""}`}
                  onClick={() => {
                    sendCommand("audio_set_background", { background_id: bg.id });
                    setShowBackgrounds(false);
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Icon name={bg.is_image ? "image" : "gradient"} size={18} />
                    {bg.title}
                  </span>
                  <span style={{ color: "var(--text-muted)" }}>
                    {bg.is_image ? t("coach.backgroundImageTag") : t("coach.backgroundVideoTag")}
                  </span>
                </button>
              ))}
            </div>
            <button className="btn btn-secondary" style={{ height: "48px", marginTop: "12px" }} onClick={() => setShowBackgrounds(false)}>
              {t("coach.close")}
            </button>
          </div>
        </div>
      )}

      {/* Bottom sheet Pistes (sur smartphone) */}
      {showTrackList && (
        <div className="coach-sheet-overlay" onClick={() => setShowTrackList(false)}>
          <div className="coach-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="coach-sheet-handle" />
            <h3 style={{ margin: "0 0 12px" }}>{t("coach.courseTracksTitle")}</h3>
            <div className="coach-sheet-list">
              {tracks.map((track, idx) => (
                <button
                  key={track.id}
                  className={`coach-sheet-track olc-press ${idx === trackIndex ? "active" : ""}`}
                  onClick={() => {
                    sendCommand("audio_jump_to_track", { index: idx });
                    setShowTrackList(false);
                  }}
                >
                  <span>{idx + 1}. {track.title}</span>
                  <span style={{ color: "var(--text-muted)" }}>{formatTime(track.duration_seconds)}</span>
                </button>
              ))}
            </div>
            <button className="btn btn-secondary" style={{ height: "48px", marginTop: "12px" }} onClick={() => setShowTrackList(false)}>
              {t("coach.close")}
            </button>
          </div>
        </div>
      )}

      {navSheet}
    </div>
  );
}
