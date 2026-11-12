"use client";

import React from "react";
import Icon from "@/components/Icon";
import { courseThumbSrc, formatClock, type CourseLike } from "@/lib/courseMeta";

interface CourseCardProps {
  course: Pick<CourseLike, "id" | "title" | "program" | "release" | "duration_seconds" | "thumbnail_url" | "thumbnail_path">;
  getApiUrl: (path: string) => string;
  variant?: "row" | "hero";
  selected?: boolean;
  onClick?: () => void;
  fallbackProgram?: string;
  children?: React.ReactNode;
  releaseLabel?: (release: string) => string;
  trailing?: React.ReactNode;
  className?: string;
}

export default function CourseCard({
  course,
  getApiUrl,
  variant = "row",
  selected = false,
  onClick,
  fallbackProgram,
  children,
  releaseLabel = (r) => `#${r}`,
  trailing,
  className = "",
}: CourseCardProps) {
  const thumb = courseThumbSrc(getApiUrl, course);
  const program = course.program || fallbackProgram;
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={`course-card course-card--${variant}${selected ? " is-selected" : ""}${onClick ? " olc-press" : ""} ${className}`.trim()}
    >
      <span className="course-card__thumb">
        {/* eslint-disable-next-line @next/next/no-img-element -- miniature servie par l'API locale, export statique */}
        {thumb ? <img src={thumb} alt="" loading="lazy" /> : <Icon name="movie" size={variant === "hero" ? 40 : 24} style={{ opacity: 0.35 }} />}
        {course.duration_seconds ? <span className="course-card__duration">{formatClock(course.duration_seconds)}</span> : null}
      </span>
      <span className="course-card__body">
        <span className="course-card__title">{course.title}</span>
        <span className="course-card__meta">
          {program ? <span className="course-card__chip">{program}</span> : null}
          {course.release ? <span className="course-card__release">{releaseLabel(course.release)}</span> : null}
        </span>
        {children}
      </span>
      {trailing}
    </Tag>
  );
}
