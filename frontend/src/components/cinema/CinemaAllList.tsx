"use client";

import React from "react";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import { formatMinutes } from "@/lib/format";
import Icon from "@/components/Icon";
import MarqueeText from "@/components/MarqueeText";

const CinemaAllList = React.memo(function CinemaAllList({
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
        const accent = "var(--accent-text)";
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
              <MarqueeText text={v.title} className="cinema-all-title" />
              <span className="cinema-all-meta" style={{ color: accent }}>
                {[v.program, formatMinutes(v.duration_seconds)].filter(Boolean).join(" · ")}
              </span>
            </div>
            <Icon name="play_circle" size={26} color="var(--text-dim)" />
          </button>
        );
      })}
    </div>
  );
});

export default CinemaAllList;
