"use client";

import React, { useCallback, useEffect, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useHoverSound } from "@/lib/useHoverSound";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
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
        <h2 style={{ color: "var(--accent-primary)" }}>{programName}</h2>
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
  const { t } = useAppSettings();
  const [videos, setVideos] = useState<CinemaVideo[]>([]);
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Toujours le canal câblé : /grid n'a de sens que pour piloter la sortie
  // câblée (ex. la sortie HDMI de la tablette Android) - pas de variante
  // réseau pour l'instant (périmètre du Lot 14, décision explicite).
  const { sendCommand } = usePlaybackSocket(undefined, undefined, "cable");
  const playHoverSound = useHoverSound("/sounds/survole.mp3");
  const themeFg = useThemeAccentForeground();

  // Même sondage que /cinema (15s) - dupliqué plutôt que partagé, cf.
  // commentaire en tête de fichier.
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch(getApiUrl("/videos?sort_by=title&order=asc"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : []))
        .then((data: CinemaVideo[]) => {
          if (cancelled || !Array.isArray(data)) return;
          setVideos((prev) =>
            prev.length === data.length && prev.every((v, i) => v.id === data[i]?.id) ? prev : data,
          );
        })
        .catch(() => {});
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Lancement distant (Lot 14) : envoie l'ordre sur le canal câblé plutôt
  // que de lire quoi que ce soit ici - cette page ne quitte JAMAIS son
  // propre affichage de grille.
  const handleSelect = useCallback((video: CinemaVideo) => {
    sendCommand("cinema_command", { action: "launch", video_id: video.id });
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

  return (
    <div className="cinema-root">
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
              // eslint-disable-next-line @next/next/no-img-element
              <img className="cinema-hero-backdrop" src={featuredThumb} alt="" />
            )}
            <div className="cinema-hero-scrim" />
            <div className="cinema-hero-content">
              <AppLogo size={72} className="cinema-brand" />
              <span className="cinema-hero-badge" style={{ color: themeFg }}>{t("cinema.featured")}</span>
              <h1 className="cinema-hero-title">{featured.title}</h1>
              <p className="cinema-hero-meta">
                {[featured.program, featured.release, formatDurationMin(featured.duration_seconds)]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <button className="cinema-hero-play grid-hero-play" style={{ color: themeFg }} onClick={() => handleSelect(featured)}>
                <Icon name="play_arrow" size={26} color={themeFg} filled />
                {t("cinema.launchCourse")}
              </button>
            </div>
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
