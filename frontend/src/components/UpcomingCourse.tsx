"use client";

import Icon from "@/components/Icon";
import { formatMinutes } from "@/lib/format";
import { thumbnailUrl } from "@/lib/thumbnail";
import type { UpcomingOccurrence } from "@/lib/upcoming";

interface Props {
  occurrence: UpcomingOccurrence;
  fallbackTitle: string;
  when: string;
  variant?: "row" | "stage" | "compact";
  label?: string;
}

export default function UpcomingCourse({ occurrence, fallbackTitle, when, variant = "row", label }: Props) {
  const thumb = thumbnailUrl(occurrence.thumbnail_path);
  const meta = [occurrence.program, formatMinutes(occurrence.duration_seconds)].filter(Boolean).join(" · ");
  return (
    <div className={`upcoming-course upcoming-course--${variant}`}>
      <div className="upcoming-course__thumb">
        {thumb ? <img src={thumb} alt="" loading="lazy" /> : <Icon name="event" size={variant === "stage" ? 40 : 22} />}
      </div>
      <div className="upcoming-course__text">
        {label && <span className="upcoming-course__label">{label}</span>}
        <span className="upcoming-course__title">{occurrence.title ?? fallbackTitle}</span>
        {meta && <span className="upcoming-course__meta">{meta}</span>}
      </div>
      <span className="upcoming-course__when">{when}</span>
    </div>
  );
}
