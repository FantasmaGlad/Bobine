"use client";

import React, { useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { RadioTrackInfo } from "@/lib/useRadioSocket";

// File « À suivre » d'une sortie radio : une vraie petite barre de gestion par morceau (pochette,
// titre, artiste, style, durée) avec glisser-déposer pour réordonner. Le glisser-déposer utilise les
// évènements « pointer » (souris, doigt, stylet) plutôt que l'API HTML5 de glisser-déposer, qui ne
// fonctionne pas au toucher (tablette Android, téléphone) ; la poignée est aussi pilotable au clavier
// (flèches haut/bas) pour l'accessibilité et la télécommande.

/** Marge (px) du bord de la liste qui déclenche le défilement automatique pendant un glissement. */
const AUTOSCROLL_EDGE = 36;
const AUTOSCROLL_STEP = 14;
/** Durée (ms) pendant laquelle l'ordre local prime sur l'état serveur après un déplacement. */
const OPTIMISTIC_HOLD_MS = 1500;

function formatTrackTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "--:--";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

interface RadioQueueListProps {
  /** Pistes À VENIR, dans l'ordre de lecture. */
  tracks: RadioTrackInfo[];
  /** Index absolu (dans l'ordre complet du moteur) de la première piste de `tracks`. */
  baseIndex: number;
  getApiUrl: (path: string) => string;
  onRemove: (absoluteIndex: number) => void;
  onMove: (fromAbsoluteIndex: number, toAbsoluteIndex: number) => void;
}

interface DragState {
  from: number;
  to: number;
  startY: number;
  startScroll: number;
  dy: number;
  rowHeight: number;
  /** Bornes (bas) de chaque ligne au DÉBUT du glissement, en coordonnées du contenu défilant : les
   * lignes se décalent ensuite visuellement, on ne peut donc pas les relire en cours de route. */
  bottoms: number[];
}

export default function RadioQueueList({ tracks, baseIndex, getApiUrl, onRemove, onMove }: RadioQueueListProps) {
  const { t } = useAppSettings();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [drag, setDrag] = useState<DragState | null>(null);
  // Ordre local appliqué dès le dépôt (sans attendre le serveur) ; ignoré dès que l'état serveur change.
  const [override, setOverride] = useState<{ signature: string; tracks: RadioTrackInfo[] } | null>(null);
  const overrideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const focusHandleRef = useRef<number | null>(null);

  const signature = `${baseIndex}:${tracks.map((track) => track.id).join(",")}`;
  const shown = override && override.signature === signature ? override.tracks : tracks;

  useEffect(
    () => () => {
      if (overrideTimerRef.current) clearTimeout(overrideTimerRef.current);
    },
    [],
  );

  // Après un déplacement au clavier, la poignée suit la piste déplacée.
  useEffect(() => {
    if (focusHandleRef.current === null) return;
    const index = focusHandleRef.current;
    focusHandleRef.current = null;
    containerRef.current?.querySelector<HTMLElement>(`[data-handle="${index}"]`)?.focus();
  }, [shown]);

  const applyLocalMove = (from: number, to: number) => {
    const next = [...shown];
    next.splice(to, 0, next.splice(from, 1)[0]);
    setOverride({ signature, tracks: next });
    if (overrideTimerRef.current) clearTimeout(overrideTimerRef.current);
    overrideTimerRef.current = setTimeout(() => setOverride(null), OPTIMISTIC_HOLD_MS);
    onMove(baseIndex + from, baseIndex + to);
  };

  const startDrag = (event: React.PointerEvent<HTMLButtonElement>, index: number) => {
    if (event.button !== 0 && event.pointerType === "mouse") return;
    const container = containerRef.current;
    if (!container) return;
    event.preventDefault();
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Pointeur déjà relâché ou non capturable : le glissement continue sans capture (les évènements
      // de la poignée suffisent tant que le pointeur reste dessus).
    }
    const containerTop = container.getBoundingClientRect().top;
    const bottoms = rowRefs.current
      .slice(0, shown.length)
      .map((row) => (row ? row.getBoundingClientRect().bottom - containerTop + container.scrollTop : 0));
    const rect = rowRefs.current[index]?.getBoundingClientRect();
    setDrag({
      from: index,
      to: index,
      startY: event.clientY,
      startScroll: container.scrollTop,
      dy: 0,
      rowHeight: (rect?.height ?? 56) + 8,
      bottoms,
    });
  };

  const moveDrag = (event: React.PointerEvent<HTMLButtonElement>) => {
    const container = containerRef.current;
    if (!drag || !container) return;
    const bounds = container.getBoundingClientRect();
    if (event.clientY < bounds.top + AUTOSCROLL_EDGE) container.scrollTop -= AUTOSCROLL_STEP;
    else if (event.clientY > bounds.bottom - AUTOSCROLL_EDGE) container.scrollTop += AUTOSCROLL_STEP;
    // Position du pointeur dans le contenu défilant : cible = première ligne dont le bas la dépasse.
    const contentY = event.clientY - bounds.top + container.scrollTop;
    let to = drag.bottoms.findIndex((bottom) => contentY < bottom);
    if (to < 0) to = Math.max(0, shown.length - 1);
    // La ligne tenue suit le pointeur même quand la liste défile.
    const dy = event.clientY - drag.startY + (container.scrollTop - drag.startScroll);
    setDrag({ ...drag, to, dy });
  };

  const endDrag = (event: React.PointerEvent<HTMLButtonElement>, commit: boolean) => {
    if (!drag) return;
    try {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // rien à libérer
    }
    const { from, to } = drag;
    setDrag(null);
    if (commit && to !== from) applyLocalMove(from, to);
  };

  const handleHandleKey = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    const delta = event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0;
    if (!delta) return;
    event.preventDefault();
    const to = index + delta;
    if (to < 0 || to >= shown.length) return;
    focusHandleRef.current = to;
    applyLocalMove(index, to);
  };

  // Décalage visuel des lignes pendant un glissement : celles que la ligne déplacée enjambe s'écartent.
  const offsetFor = (index: number): number => {
    if (!drag) return 0;
    if (index === drag.from) return drag.dy;
    if (drag.from < drag.to && index > drag.from && index <= drag.to) return -drag.rowHeight;
    if (drag.from > drag.to && index >= drag.to && index < drag.from) return drag.rowHeight;
    return 0;
  };

  return (
    <div ref={containerRef} className={`rq-list${drag ? " is-sorting" : ""}`} role="list">
      {shown.map((track, i) => {
        const cover = track.cover_url ? getApiUrl(track.cover_url) : null;
        const absolute = baseIndex + i;
        const isDragged = drag?.from === i;
        return (
          <div
            key={`${absolute}-${track.id}`}
            ref={(node) => {
              rowRefs.current[i] = node;
            }}
            role="listitem"
            className={`rq-row${isDragged ? " is-dragging" : ""}`}
            style={{
              transform: offsetFor(i) ? `translateY(${offsetFor(i)}px)` : undefined,
              transition: isDragged ? "none" : "transform 140ms ease",
            }}
          >
            <button
              type="button"
              className="rq-handle"
              data-handle={i}
              aria-label={t("radioRemote.dragHandle", { title: track.title })}
              title={t("radioRemote.dragHandleHint")}
              onPointerDown={(event) => startDrag(event, i)}
              onPointerMove={moveDrag}
              onPointerUp={(event) => endDrag(event, true)}
              onPointerCancel={(event) => endDrag(event, false)}
              onKeyDown={(event) => handleHandleKey(event, i)}
            >
              <Icon name="drag_indicator" size={20} />
            </button>
            <span className="rq-pos">{i + 1}</span>
            {cover ? (
              // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API locale, export statique
              <img className="rq-cover" src={cover} alt="" loading="lazy" draggable={false} />
            ) : (
              <span className="rq-cover rq-cover--empty" aria-hidden="true">
                <Icon name="music_note" size={20} style={{ opacity: 0.4 }} />
              </span>
            )}
            <span className="rq-text">
              <span className="rq-title">{track.title}</span>
              <span className="rq-sub">
                <span className="rq-artist">{track.artist || t("radioLibrary.unknownArtist")}</span>
                {track.genre ? <span className="rq-genre">{track.genre}</span> : null}
              </span>
            </span>
            <span className="rq-duration">{formatTrackTime(track.duration_seconds)}</span>
            <button
              type="button"
              className="rq-remove olc-press"
              aria-label={t("radioRemote.removeTrack", { title: track.title })}
              title={t("radioRemote.remove")}
              onClick={() => onRemove(absolute)}
            >
              <Icon name="close" size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
