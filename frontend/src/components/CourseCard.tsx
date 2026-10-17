"use client";

import React from "react";
import Icon from "@/components/Icon";
import { courseThumbSrc, formatClock, type CourseLike } from "@/lib/courseMeta";

interface CourseCardProps {
  course: Pick<CourseLike, "id" | "title" | "program" | "release" | "duration_seconds" | "thumbnail_url" | "thumbnail_path">;
  getApiUrl: (path: string) => string;
  /** row : vignette à gauche (listes) ; hero : vignette pleine largeur en tête. */
  variant?: "row" | "hero";
  selected?: boolean;
  onClick?: () => void;
  /** Libellé affiché quand le cours n'a pas de programme. */
  fallbackProgram?: string;
  /** Pied de carte (boutons, progression). */
  children?: React.ReactNode;
  /** Texte de la release : "Rel. 120". */
  releaseLabel?: (release: string) => string;
  /** Accessoire à droite de la ligne (case à cocher, coche de sélection). */
  trailing?: React.ReactNode;
  className?: string;
}

/**
 * Représentation commune d'un cours : miniature, titre, programme, release et
 * durée. Une seule présentation pour la liste de lancement, l'aperçu avant
 * lancement et la carte « en cours » de la télécommande.
 */
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
