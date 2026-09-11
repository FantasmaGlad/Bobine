"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useHoverSound } from "@/lib/useHoverSound";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
import { useScreenWakeLock } from "@/lib/useScreenWakeLock";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";

// Lot 14 (cf. docs/plan-implementation-android.md) : écran de sélection
// SEUL — reprend la présentation visuelle de la grille de `/cinema` (héros
// + rangées par programme + liste complète), mais sans jamais lire de
// vidéo localement. Sélectionner un cours envoie une commande `launch` sur
// le canal câblé plutôt que de démarrer une lecture ici — c'est le(s)
// `/cinema` du même canal qui joue(nt) réellement le cours (ex. la sortie
// HDMI de la tablette Android). Cette page reste TOUJOURS affichée sur la
// grille, y compris pendant qu'un cours joue ailleurs sur le canal.
//
// Duplique volontairement quelques petits utilitaires (`getApiUrl`,
// `thumbnailUrl`, `formatDurationMin`, `CinemaRow`, `CinemaAllList`)
// plutôt que de les extraire de `cinema/page.tsx` dans un module partagé :
// cohérent avec la convention déjà en place dans ce dépôt (chaque route a
// sa propre petite fonction `getApiUrl`, jamais un utilitaire central) et
// évite tout risque de régression sur `/cinema`, qui reste inchangé à part
// l'ajout de la commande `launch` (cf. Découvertes du Lot 14).

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

interface CinemaVideo {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  thumbnail_path: string | null;
}

function formatDurationMin(seconds: number | null) {
  if (!seconds) return "";
  return `${Math.round(seconds / 60)} min`;
}

function formatClock(date: Date) {
  return `${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
}

function formatTime(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function thumbnailUrl(video: CinemaVideo): string | null {
  if (!video.thumbnail_path) return null;
  const filename = video.thumbnail_path.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

const ROW_SCROLL_FRACTION = 0.85;

const GridRow = React.memo(function GridRow({
  programName,
  items,
  rowIndex,
  onSelect,
  onHover,
  coursesCountLabel,
}: {
  programName: string;
  items: CinemaVideo[];
  rowIndex: number;
  onSelect: (video: CinemaVideo) => void;
  onHover: () => void;
  coursesCountLabel: string;
}) {
  const scrollRef = React.useRef<HTMLDivElement | null>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateArrows = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    updateArrows();
    const el = scrollRef.current;
    if (!el) return;
    const onResize = () => updateArrows();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [updateArrows, items.length]);

  const scrollBy = (direction: 1 | -1) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: direction * el.clientWidth * ROW_SCROLL_FRACTION, behavior: "smooth" });
  };

  return (
    <section className="cinema-row" style={{ animationDelay: `${rowIndex * 90}ms` }}>
      <div className="cinema-row-header">
        <h2>{programName}</h2>
        <span className="cinema-row-count">{coursesCountLabel}</span>
      </div>
      <div className="cinema-row-wrap">
        {canScrollLeft && (
          <button className="cinema-row-arrow cinema-row-arrow-left" onClick={() => scrollBy(-1)} aria-label="Précédent">
            <Icon name="chevron_left" size={32} />
          </button>
        )}
        <div className="cinema-row-scroll" ref={scrollRef} onScroll={updateArrows}>
          {items.map((v, i) => {
            const thumb = thumbnailUrl(v);
            return (
              <button
                key={v.id}
                className="cinema-card"
                style={{ animationDelay: `${rowIndex * 90 + i * 45}ms` }}
                onClick={() => onSelect(v)}
                onMouseEnter={onHover}
                title={v.title}
              >
                <div className="cinema-card-thumb">
                  {thumb ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={thumb} alt="" loading="lazy" />
                  ) : (
                    <div className="cinema-card-thumb-fallback">
                      <Icon name="movie" size={40} color="var(--text-dim)" />
                    </div>
                  )}
                  <span className="cinema-card-play">
                    <Icon name="play_arrow" size={34} filled />
                  </span>
                  {v.duration_seconds ? (
                    <span className="cinema-card-duration">{formatDurationMin(v.duration_seconds)}</span>
                  ) : null}
                </div>
                <span className="cinema-card-title">{v.title}</span>
                <span className="cinema-card-meta">{v.release ?? ""}</span>
              </button>
            );
          })}
        </div>
        {canScrollRight && (
          <button className="cinema-row-arrow cinema-row-arrow-right" onClick={() => scrollBy(1)} aria-label="Suivant">
            <Icon name="chevron_right" size={32} />
          </button>
        )}
      </div>
    </section>
  );
});

const GridAllList = React.memo(function GridAllList({
  videos,
  onSelect,
  onHover,
}: {
  videos: CinemaVideo[];
  onSelect: (video: CinemaVideo) => void;
  onHover: () => void;
}) {
  return (
    <div className="cinema-all-grid">
      {videos.map((v, i) => {
        const thumb = thumbnailUrl(v);
        const accent = "var(--accent-primary)";
        return (
          <button
            key={v.id}
            className="cinema-all-item"
            style={{ animationDelay: `${i * 30}ms` }}
            onClick={() => onSelect(v)}
            onMouseEnter={onHover}
          >
            <div className="cinema-all-thumb">
              {thumb ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={thumb} alt="" loading="lazy" />
              ) : (
                <Icon name="movie" size={22} color="var(--text-dim)" />
              )}
            </div>
            <div className="cinema-all-text">
              <span className="cinema-all-title">{v.title}</span>
              <span className="cinema-all-meta" style={{ color: accent }}>
                {[v.program, formatDurationMin(v.duration_seconds)].filter(Boolean).join(" · ")}
              </span>
            </div>
            <Icon name="play_circle" size={26} color="var(--text-dim)" />
          </button>
        );
      })}
    </div>
  );
});

export default function GridPage() {
  const { t, wiredDisplayMode, setWiredDisplayMode } = useAppSettings();
  useScreenWakeLock(true);
  const [videos, setVideos] = useState<CinemaVideo[]>([]);
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Toujours le canal câblé : /grid n'a de sens que pour piloter la sortie
  // câblée (ex. la sortie HDMI de la tablette Android) - pas de variante
  // réseau pour l'instant (périmètre du Lot 14, décision explicite).
  const { sendCommand, displayOutputCable, cinemaState, libraryVersion } = usePlaybackSocket(undefined, undefined, "cable");
  // Avertissement "rien ne se passe" (retour utilisateur) : un ordre "launch"
  // envoyé alors que la sortie câblée est réglée sur "kiosk" (et non
  // "cinema") ne sera reçu par AUCUN écran - /kiosk n'écoute pas
  // cinema_command. displayOutputCable est déjà suivi par usePlaybackSocket
  // pour un tout autre usage (redirection de /cinema) ; le réutiliser ici en
  // lecture seule coûte zéro requête supplémentaire. Purement indicatif :
  // la commande part quand même (displayOutputCable peut être momentanément
  // périmé/null au tout premier rendu).
  const [launchWarning, setLaunchWarning] = useState<string | null>(null);
  const launchWarningTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const playHoverSound = useHoverSound("/sounds/survole.mp3");
  const themeFg = useThemeAccentForeground();

  // Même sondage que /cinema (15s) - dupliqué plutôt que partagé, cf.
  // commentaire en tête de fichier.
  // Réf. retour utilisateur "/grid n'affiche aucune vidéo" (2026-09-11) :
  // un échec transitoire (backend momentanément congestionné, cf.
  // docs/audit-android-2026-09-11.md §C1) laissait `videos` vide jusqu'au
  // PROCHAIN sondage à 15s — ressenti comme "il faut recharger plusieurs
  // fois". Retentative rapide (3s) dédiée sur ÉCHEC uniquement, en plus du
  // sondage normal ; ne vide JAMAIS une liste déjà chargée sur un échec
  // (une réponse invalide/une erreur réseau ponctuelle garde l'affichage
  // précédent plutôt que de faire disparaître la grille).
  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    const load = () => {
      fetch(getApiUrl("/videos?sort_by=title&order=asc"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
        .then((data: CinemaVideo[]) => {
          if (cancelled || !Array.isArray(data)) return;
          setVideos((prev) => {
            const isSame =
              prev.length === data.length &&
              prev.every((v, i) => {
                const d = data[i];
                return (
                  d &&
                  v.id === d.id &&
                  v.title === d.title &&
                  v.program === d.program &&
                  v.release === d.release &&
                  v.duration_seconds === d.duration_seconds &&
                  v.thumbnail_path === d.thumbnail_path
                );
              });
            return isSame ? prev : data;
          });
        })
        .catch(() => {
          if (cancelled) return;
          if (retryTimer) clearTimeout(retryTimer);
          retryTimer = setTimeout(load, 3000);
        });
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
      if (retryTimer) clearTimeout(retryTimer);
    };
    // libraryVersion : recharge immédiate sur `library_change` (import/
    // modif/suppression), au lieu d'attendre jusqu'à 15s.
  }, [libraryVersion]);

  // Lancement distant (Lot 14) : envoie l'ordre sur le canal câblé plutôt
  // que de lire quoi que ce soit ici - cette page ne quitte JAMAIS son
  // propre affichage de grille.
  const handleSelect = useCallback((video: CinemaVideo) => {
    sendCommand("cinema_command", { action: "launch", video_id: video.id });
    if (displayOutputCable !== null && displayOutputCable !== "cinema") {
      setLaunchWarning(t("cinema.gridNoScreen"));
      if (launchWarningTimerRef.current) clearTimeout(launchWarningTimerRef.current);
      launchWarningTimerRef.current = setTimeout(() => setLaunchWarning(null), 6000);
    }
  }, [sendCommand, displayOutputCable, t]);

  useEffect(() => {
    return () => {
      if (launchWarningTimerRef.current) clearTimeout(launchWarningTimerRef.current);
    };
  }, []);

  // Panneau "en cours de lecture" (demande explicite utilisateur : avancer/
  // reculer/pause/enlever depuis /grid, l'écran HDMI n'affiche plus aucune
  // commande) — même mécanique que le bloc "cinéma" du tableau de bord admin
  // (DashboardScreen.tsx) : `cinemaState` est le rapport passif que /cinema
  // envoie déjà sur ce canal (titre/position/lecture), et les commandes
  // play/pause/seek/stop empruntent le même `cinema_command` que "launch".
  // Dupliqué plutôt que partagé, cf. commentaire en tête de fichier.
  const [nowPlayingTick, setNowPlayingTick] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowPlayingTick(Date.now()), 250);
    return () => clearInterval(id);
  }, []);
  const cinemaReceivedAtRef = React.useRef(0);
  const [pendingPlaying, setPendingPlaying] = useState<boolean | null>(null);
  const [optimisticSeek, setOptimisticSeek] = useState<{ position: number; timestamp: number } | null>(null);
  const optimisticTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    cinemaReceivedAtRef.current = Date.now();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réaction à un rapport externe, le rapport redevient la vérité
    setPendingPlaying(null);
    setOptimisticSeek((current) => {
      if (!current) return null;
      const elapsed = (Date.now() - current.timestamp) / 1000;
      const expected = current.position + (cinemaState?.playing ? elapsed : 0);
      if (Math.abs((cinemaState?.position_seconds ?? 0) - expected) < 2.5 || elapsed > 1.2) {
        return null;
      }
      return current;
    });
  }, [cinemaState]);

  useEffect(() => {
    return () => {
      if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
    };
  }, []);

  // Périmé après 8s sans nouveau rapport (même seuil que DashboardScreen) :
  // /cinema rapporte toutes les 2s, un dépassement signale un écran fermé/
  // déconnecté plutôt qu'une lecture qui existe encore.
  const nowPlayingRaw =
    cinemaState && cinemaState.title && nowPlayingTick - cinemaReceivedAtRef.current < 8000 ? cinemaState : null;
  const isPlayingEffective = pendingPlaying ?? nowPlayingRaw?.playing ?? false;
  const computedPosition = optimisticSeek
    ? Math.min(
        nowPlayingRaw?.duration_seconds || Infinity,
        optimisticSeek.position +
          (isPlayingEffective ? Math.max(0, (nowPlayingTick - optimisticSeek.timestamp) / 1000) : 0),
      )
    : nowPlayingRaw
    ? Math.min(
        nowPlayingRaw.duration_seconds || Infinity,
        nowPlayingRaw.position_seconds +
          (nowPlayingRaw.playing ? Math.max(0, (nowPlayingTick - cinemaReceivedAtRef.current) / 1000) : 0),
      )
    : 0;

  const nowPlaying = nowPlayingRaw
    ? {
        ...nowPlayingRaw,
        playing: isPlayingEffective,
        position_seconds: computedPosition,
      }
    : null;
  const [nowPlayingSeekDrag, setNowPlayingSeekDrag] = useState<number | null>(null);

  const handleNowPlayingPlayPause = useCallback(() => {
    if (!nowPlaying) return;
    const next = !nowPlaying.playing;
    setPendingPlaying(next);
    sendCommand("cinema_command", { action: next ? "play" : "pause" });
  }, [nowPlaying, sendCommand]);

  const handleNowPlayingSeekDelta = useCallback((delta: number) => {
    if (!nowPlaying) return;
    const currentBase = optimisticSeek ? optimisticSeek.position : nowPlaying.position_seconds;
    const target = Math.max(0, Math.min(currentBase + delta, nowPlaying.duration_seconds || Infinity));
    const now = Date.now();
    setOptimisticSeek({ position: target, timestamp: now });
    if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
    optimisticTimerRef.current = setTimeout(() => {
      setOptimisticSeek(null);
    }, 2000);
    sendCommand("cinema_command", { action: "seek", position_seconds: target });
  }, [nowPlaying, optimisticSeek, sendCommand]);

  const handleNowPlayingStop = useCallback(() => {
    sendCommand("cinema_command", { action: "stop" });
  }, [sendCommand]);

  const [scrambleTick, setScrambleTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setScrambleTick((v) => v + 1), 60_000);
    return () => clearInterval(id);
  }, []);
  const SCRAMBLE_INTERVAL_MS = 15 * 60 * 1000;
  const featured = React.useMemo(() => {
    if (videos.length === 0) return null;
    const bucket = Math.floor(Date.now() / SCRAMBLE_INTERVAL_MS);
    const hash = Math.abs((bucket * 2654435761) % videos.length);
    return videos[hash];
    // eslint-disable-next-line react-hooks/exhaustive-deps -- scrambleTick ne sert qu'à forcer le recalcul périodique
  }, [videos, scrambleTick]);
  const featuredThumb = featured ? thumbnailUrl(featured) : null;

  const rows = React.useMemo(() => {
    const byProgram = new Map<string, CinemaVideo[]>();
    for (const v of videos) {
      const key = v.program || t("cinema.otherProgram");
      if (!byProgram.has(key)) byProgram.set(key, []);
      byProgram.get(key)!.push(v);
    }
    return [...byProgram.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [videos, t]);

  if (wiredDisplayMode === "headless") {
    return (
      <div className="grid-standby-root">
        <div className="grid-standby-card">
          <div className="grid-standby-header">
            <AppLogo size={48} className="grid-standby-logo" />
            <span className="grid-standby-clock">{formatClock(now)}</span>
          </div>

          <div className="grid-standby-content">
            <h1 className="grid-standby-title">{t("settingsPage.gridStandbyTitle")}</h1>
            <p className="grid-standby-subtitle">{t("settingsPage.gridStandbySubtitle")}</p>

            <div className="grid-standby-status-box">
              <div className="grid-standby-status-badge">
                <span className="grid-standby-pulse-dot" />
                <Icon name="tv" size={20} />
                <span>{t("settingsPage.gridStandbyHdmiActive")}</span>
              </div>
              <p className="grid-standby-status-desc">{t("settingsPage.gridStandbyHdmiHelp")}</p>
              {nowPlaying && (
                <div className="grid-standby-now-playing">
                  <span className="grid-standby-now-playing-label">{t("cinema.nowPlaying")} :</span>
                  <strong className="grid-standby-now-playing-title">{nowPlaying.title}</strong>
                  {nowPlaying.duration_seconds ? (
                    <span className="grid-standby-now-playing-time">
                      ({formatTime(nowPlaying.position_seconds)} / {formatTime(nowPlaying.duration_seconds)})
                    </span>
                  ) : null}
                </div>
              )}
            </div>

            <div className="grid-standby-actions">
              <button
                type="button"
                className="btn btn-primary grid-standby-btn-main"
                style={{ color: themeFg }}
                onClick={() => setWiredDisplayMode("dual_screen")}
              >
                <Icon name="devices" size={22} color={themeFg} />
                <span>{t("settingsPage.gridStandbySwitchToDual")}</span>
              </button>
              <p className="grid-standby-action-hint">{t("settingsPage.gridStandbySwitchToDualHelp")}</p>

              <a href="/" className="btn btn-secondary grid-standby-btn-admin">
                <Icon name="settings" size={18} />
                <span>{t("settingsPage.gridStandbyOpenAdmin")}</span>
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="cinema-root">
      {launchWarning && <div className="grid-launch-warning">{launchWarning}</div>}
      {videos.length === 0 && (
        <div className="cinema-empty-screen">
          <AppLogo className="cinema-empty-logo" />
          <span className="cinema-empty-clock">{formatClock(now)}</span>
          <span className="cinema-empty-message">{t("cinema.empty")}</span>
        </div>
      )}

      <div className="cinema-layer cinema-grid-layer visible">
        {featured && (
          <section className="cinema-hero">
            {featuredThumb && (
              <div className="cinema-hero-backdrop-wrap">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img className="cinema-hero-backdrop" src={featuredThumb} alt="" />
              </div>
            )}
            {/* Masque de transition Netflix : fondu horizontal opaque couleur thème vers miniature + fondu vers le bas */}
            <div className="cinema-hero-scrim" />
            <div className="cinema-hero-content">
              <div className="cinema-hero-brand-row">
                <AppLogo size={110} className="cinema-brand-logo" />
              </div>
              <h1 className="cinema-hero-title">{featured.title}</h1>
              <div className="cinema-hero-meta-row">
                {featured.program && (
                  <span className="cinema-hero-program-tag">{featured.program}</span>
                )}
                {featured.release && (
                  <span className="cinema-hero-year">{featured.release}</span>
                )}
                {featured.duration_seconds && (
                  <span className="cinema-hero-duration">{formatDurationMin(featured.duration_seconds)}</span>
                )}
                <span className="cinema-hero-badge-pill">4K Ultra HD</span>
                <span className="cinema-hero-badge-pill">Stéréo 5.1</span>
              </div>
              <div className="cinema-hero-actions">
                <button className="cinema-hero-play" style={{ color: themeFg }} onClick={() => handleSelect(featured)}>
                  <Icon name="play_arrow" size={28} color={themeFg} filled />
                  {t("cinema.launchCourse")}
                </button>
              </div>
            </div>

            {/* Widget "en cours de lecture" (demande explicite : style Apple,
                à droite du titre, aucune couleur rouge - tout suit le thème
                actif). Rendu comme second enfant flex de .cinema-hero, à côté
                de .cinema-hero-content plutôt qu'au-dessus de toute la page. */}
            {nowPlaying && (
              <section className="grid-now-playing">
                <button
                  className="grid-now-playing-close"
                  onClick={handleNowPlayingStop}
                  title={t("cinema.removeCourse")}
                  aria-label={t("cinema.removeCourse")}
                >
                  <Icon name="close" size={18} />
                </button>
                <span className="grid-now-playing-label">{t("cinema.nowPlaying")}</span>
                <h2 className="grid-now-playing-title">{nowPlaying.title}</h2>
                <input
                  type="range"
                  className="grid-now-playing-seek"
                  min={0}
                  max={nowPlaying.duration_seconds || 0}
                  step={1}
                  value={nowPlayingSeekDrag ?? nowPlaying.position_seconds}
                  onChange={(e) => setNowPlayingSeekDrag(Number(e.target.value))}
                  onMouseUp={(e) => {
                    const value = Number((e.target as HTMLInputElement).value);
                    const now = Date.now();
                    setOptimisticSeek({ position: value, timestamp: now });
                    if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
                    optimisticTimerRef.current = setTimeout(() => setOptimisticSeek(null), 2000);
                    sendCommand("cinema_command", { action: "seek", position_seconds: value });
                    setNowPlayingSeekDrag(null);
                  }}
                  onTouchEnd={(e) => {
                    const value = Number((e.target as HTMLInputElement).value);
                    const now = Date.now();
                    setOptimisticSeek({ position: value, timestamp: now });
                    if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
                    optimisticTimerRef.current = setTimeout(() => setOptimisticSeek(null), 2000);
                    sendCommand("cinema_command", { action: "seek", position_seconds: value });
                    setNowPlayingSeekDrag(null);
                  }}
                />
                <div className="grid-now-playing-times">
                  <span>{formatTime(nowPlayingSeekDrag ?? nowPlaying.position_seconds)}</span>
                  <span>{formatTime(nowPlaying.duration_seconds)}</span>
                </div>
                <div className="grid-now-playing-controls">
                  <button
                    className="grid-now-playing-btn"
                    onClick={() => handleNowPlayingSeekDelta(-10)}
                    title={t("cinema.seekBack")}
                    aria-label={t("cinema.seekBack")}
                  >
                    <Icon name="replay_10" size={26} />
                  </button>
                  <button
                    className="grid-now-playing-btn grid-now-playing-btn-main"
                    onClick={handleNowPlayingPlayPause}
                    title={nowPlaying.playing ? t("cinema.pause") : t("cinema.play")}
                  >
                    <Icon name={nowPlaying.playing ? "pause" : "play_arrow"} size={30} filled />
                  </button>
                  <button
                    className="grid-now-playing-btn"
                    onClick={() => handleNowPlayingSeekDelta(10)}
                    title={t("cinema.seekForward")}
                    aria-label={t("cinema.seekForward")}
                  >
                    <Icon name="forward_10" size={26} />
                  </button>
                </div>
              </section>
            )}
          </section>
        )}

        <div className="cinema-sections">
          <p className="cinema-subtitle">{t("cinema.subtitle")}</p>
          {rows.length === 0 && videos.length > 0 && <p className="cinema-empty">{t("cinema.empty")}</p>}

          {rows.map(([programName, items], rowIndex) => (
            <GridRow
              key={programName}
              programName={programName}
              items={items}
              rowIndex={rowIndex}
              onSelect={handleSelect}
              onHover={playHoverSound}
              coursesCountLabel={t("cinema.coursesCount", { count: items.length })}
            />
          ))}

          {videos.length > 0 && (
            <section className="cinema-all">
              <h2>{t("cinema.allCourses")}</h2>
              <GridAllList videos={videos} onSelect={handleSelect} onHover={playHoverSound} />
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
