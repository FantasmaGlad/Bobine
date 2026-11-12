"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import { formatMinutes } from "@/lib/format";
import Icon from "@/components/Icon";
import MarqueeText from "@/components/MarqueeText";

const ROW_SCROLL_FRACTION = 0.85;

const CinemaRow = React.memo(function CinemaRow({
  programName,
  items,
  rowIndex,
  onSelect,
  onHover,
  coursesCountLabel,
  accentTitle = false,
}: {
  programName: string;
  items: CinemaVideo[];
  rowIndex: number;
  onSelect: (video: CinemaVideo) => void;
  onHover: () => void;
  coursesCountLabel: string;
  accentTitle?: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
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

  const { t } = useAppSettings();
  const scrollBy = (direction: 1 | -1) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: direction * el.clientWidth * ROW_SCROLL_FRACTION, behavior: "smooth" });
  };

  return (
    <section className="cinema-row" style={{ animationDelay: `${rowIndex * 90}ms` }}>
      <div className="cinema-row-header">
        <h2 style={accentTitle ? { color: "var(--accent-text)" } : undefined}>{programName}</h2>
        <span className="cinema-row-count">{coursesCountLabel}</span>
      </div>
      <div className="cinema-row-wrap">
        {canScrollLeft && (
          <button
            className="cinema-row-arrow cinema-row-arrow-left"
            onClick={() => scrollBy(-1)}
            aria-label={t("common.previous")}
          >
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
                    <span className="cinema-card-duration">{formatMinutes(v.duration_seconds)}</span>
                  ) : null}
                </div>
                <MarqueeText text={v.title} className="cinema-card-title" />
                <span className="cinema-card-meta">{v.release ?? ""}</span>
              </button>
            );
          })}
        </div>
        {canScrollRight && (
          <button
            className="cinema-row-arrow cinema-row-arrow-right"
            onClick={() => scrollBy(1)}
            aria-label="Suivant"
          >
            <Icon name="chevron_right" size={32} />
          </button>
        )}
      </div>
    </section>
  );
});

export default CinemaRow;
