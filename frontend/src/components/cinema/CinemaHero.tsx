"use client";

import React, { useState } from "react";

import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import { formatCleanDescription } from "@/lib/formatDescription";
import { formatMinutes } from "@/lib/format";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
import { getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";

interface Props {
  featured: CinemaVideo;
  onSelect: (video: CinemaVideo) => void;
  children?: React.ReactNode;
}

function Meta({ featured }: { featured: CinemaVideo }) {
  const { t } = useAppSettings();
  const resolution = getResolutionBadge(featured.width, featured.height);
  const audio = getAudioQualityBadge(featured.audio_channels, featured.audio_codec, undefined, t);
  return (
    <div className="cinema-hero-meta-row">
      {featured.program && <span className="cinema-hero-program-tag">{featured.program}</span>}
      {featured.release && <span className="cinema-hero-year">{featured.release}</span>}
      {featured.duration_seconds && <span className="cinema-hero-duration">{formatMinutes(featured.duration_seconds)}</span>}
      {resolution && <span className="cinema-hero-badge-pill">{resolution}</span>}
      {audio && <span className="cinema-hero-badge-pill">{audio}</span>}
    </div>
  );
}

export default function CinemaHero({ featured, onSelect, children }: Props) {
  const { t } = useAppSettings();
  const themeFg = useThemeAccentForeground();
  const backdrop = thumbnailUrl(featured);
  return (
    <section className="cinema-hero" data-remote-scroll-top>
      {backdrop && (
        <div className="cinema-hero-backdrop-wrap">
          <img className="cinema-hero-backdrop" src={backdrop} alt="" />
        </div>
      )}
      <div className="cinema-hero-scrim" />
      <div className="cinema-hero-content">
        <div className="cinema-hero-brand-row"><AppLogo size={110} className="cinema-brand-logo" /></div>
        <h1 className="cinema-hero-title">{featured.title}</h1>
        <Meta featured={featured} />
        {featured.description && <p className="cinema-hero-description">{formatCleanDescription(featured.description)}</p>}
        <div className="cinema-hero-actions">
          <button className="cinema-hero-play" style={{ color: themeFg }} onClick={() => onSelect(featured)}>
            <Icon name="play_arrow" size={28} color={themeFg} filled />
            {t("cinema.launchCourse")}
          </button>
        </div>
      </div>
      {children}
    </section>
  );
}

export function useHeroScroll() {
  const [scrolled, setScrolled] = useState(false);
  const onScroll = (e: React.UIEvent<HTMLElement>) => {
    const away = e.currentTarget.scrollTop > 24;
    if (away !== scrolled) setScrolled(away);
  };
  return { scrolled, onScroll };
}

export function CinemaScrollTab({ away, onOpen }: { away: boolean; onOpen: () => void }) {
  const { t } = useAppSettings();
  return (
    <button type="button" className={`cinema-scroll-hint${away ? " is-away" : ""}`} tabIndex={-1} aria-hidden={away} onClick={onOpen}>
      <span>{t("cinema.discoverCourses")}</span>
      <Icon name="expand_less" size={24} />
    </button>
  );
}
