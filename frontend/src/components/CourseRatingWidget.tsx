"use client";

import React from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { RatingConfirmed, RatingHeader, RatingProgress, RatingStars } from "./course-rating/RatingParts";
import { useCourseRating } from "./course-rating/useCourseRating";
import type { OutputId } from "@/lib/outputs";

export interface CourseRatingWidgetProps {
  videoId: number;
  courseTitle: string;
  channel?: OutputId;
  autoCloseSeconds?: number;
  onClose?: () => void;
  onRated?: (score: number) => void;
  isCinemaMode?: boolean;
}

export default function CourseRatingWidget({
  videoId,
  courseTitle,
  channel = "cable",
  autoCloseSeconds = 20,
  onClose,
  onRated,
  isCinemaMode = false,
}: CourseRatingWidgetProps) {
  const { t } = useAppSettings();
  const duration = autoCloseSeconds > 0 ? autoCloseSeconds : 20;
  const rating = useCourseRating({ videoId, channel, duration, isCinemaMode, onClose, onRated });
  const { selectedScore, hoveredScore, setHoveredScore, submitted, remainingSeconds, handleSelectScore } = rating;
  const active = hoveredScore || selectedScore || 0;
  const progressPercent = Math.max(0, Math.min(100, (remainingSeconds / duration) * 100));

  return (
    <div
      className={`course-rating-card ${isCinemaMode ? "course-rating-cinema" : "course-rating-grid"}`}
      role="region"
      aria-label={t("courseRating.title")}
    >
      <RatingHeader submitted={submitted} courseTitle={courseTitle} isCinemaMode={isCinemaMode} onClose={onClose} t={t} />
      {!submitted ? (
        <RatingStars active={active} isCinemaMode={isCinemaMode} onHover={setHoveredScore} onSelect={handleSelectScore} t={t} />
      ) : (
        <RatingConfirmed score={selectedScore || 0} isCinemaMode={isCinemaMode} t={t} />
      )}
      {!submitted && <RatingProgress percent={progressPercent} />}
    </div>
  );
}
