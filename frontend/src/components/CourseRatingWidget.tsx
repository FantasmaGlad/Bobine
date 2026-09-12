"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

export interface CourseRatingWidgetProps {
  videoId: number;
  courseTitle: string;
  sessionId?: number | null;
  channel?: "cable" | "network";
  autoCloseSeconds?: number;
  onClose?: () => void;
  onRated?: (score: number) => void;
  isCinemaMode?: boolean;
}

export default function CourseRatingWidget({
  videoId,
  courseTitle,
  sessionId,
  channel = "cable",
  autoCloseSeconds = 300,
  onClose,
  onRated,
  isCinemaMode = false,
}: CourseRatingWidgetProps) {
  const { t } = useAppSettings();
  const [selectedScore, setSelectedScore] = useState<number | null>(null);
  const [hoveredScore, setHoveredScore] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(autoCloseSeconds);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-close countdown
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          if (onClose) onClose();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [onClose]);

  const handleSelectScore = useCallback(
    async (score: number) => {
      if (submitted) return;
      setSelectedScore(score);
      setSubmitted(true);

      try {
        await fetch("/api/metrics/ratings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            video_id: videoId,
            course_title: courseTitle,
            score,
            session_id: sessionId ?? null,
            channel,
          }),
        });
      } catch (err) {
        console.error("Failed to submit rating:", err);
      }

      if (onRated) onRated(score);

      // Auto-close quickly after feedback (3.5s)
      setTimeout(() => {
        if (onClose) onClose();
      }, 3500);
    },
    [videoId, courseTitle, sessionId, channel, submitted, onRated, onClose]
  );

  // Keyboard navigation (ArrowLeft/ArrowRight to select stars, Enter to submit, Escape to close)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (onClose) onClose();
      } else if (e.key === "ArrowLeft") {
        setHoveredScore((prev) => Math.max(1, (prev || 1) - 1));
      } else if (e.key === "ArrowRight") {
        setHoveredScore((prev) => Math.min(5, (prev || 1) + 1));
      } else if (e.key === "Enter" || e.key === " ") {
        if (hoveredScore && !submitted) {
          handleSelectScore(hoveredScore);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [hoveredScore, submitted, handleSelectScore, onClose]);

  const currentActiveScore = hoveredScore || selectedScore || 0;
  const progressPercent = Math.max(0, (remainingSeconds / autoCloseSeconds) * 100);

  const getScoreLabel = (score: number) => {
    switch (score) {
      case 1:
        return t("courseRating.rating1");
      case 2:
        return t("courseRating.rating2");
      case 3:
        return t("courseRating.rating3");
      case 4:
        return t("courseRating.rating4");
      case 5:
        return t("courseRating.rating5");
      default:
        return "";
    }
  };

  return (
    <div
      className={`course-rating-card ${isCinemaMode ? "course-rating-cinema" : "course-rating-grid"}`}
      role="region"
      aria-label={t("courseRating.title")}
    >
      <div className="course-rating-header">
        <div className="course-rating-title-block">
          <h4 className="course-rating-title">
            <Icon name="star_rate" size={isCinemaMode ? 28 : 20} className="course-rating-icon-title" />
            {submitted ? t("courseRating.submitSuccess") : t("courseRating.title")}
          </h4>
          <p className="course-rating-subtitle">
            {submitted ? courseTitle : t("courseRating.subtitle")}
          </p>
        </div>
        {onClose && (
          <button
            type="button"
            className="course-rating-close-btn"
            onClick={onClose}
            aria-label={t("courseRating.close")}
            title={t("courseRating.close")}
          >
            <Icon name="close" size={isCinemaMode ? 24 : 18} />
          </button>
        )}
      </div>

      {!submitted ? (
        <div className="course-rating-stars-row">
          <div className="course-rating-stars-list">
            {[1, 2, 3, 4, 5].map((star) => {
              const isFilled = star <= currentActiveScore;
              return (
                <button
                  key={star}
                  type="button"
                  className={`course-rating-star-btn ${isFilled ? "active" : ""}`}
                  onMouseEnter={() => setHoveredScore(star)}
                  onMouseLeave={() => setHoveredScore(null)}
                  onClick={() => handleSelectScore(star)}
                  aria-label={`${star} / 5 - ${getScoreLabel(star)}`}
                >
                  <Icon
                    name={isFilled ? "star" : "star_outline"}
                    size={isCinemaMode ? 48 : 32}
                    className="course-rating-star-icon"
                  />
                </button>
              );
            })}
          </div>
          <div className="course-rating-score-label">
            {currentActiveScore > 0 ? getScoreLabel(currentActiveScore) : " "}
          </div>
        </div>
      ) : (
        <div className="course-rating-submitted-feedback">
          <div className="course-rating-confirmed-stars">
            {[1, 2, 3, 4, 5].map((star) => (
              <Icon
                key={star}
                name={star <= (selectedScore || 0) ? "star" : "star_outline"}
                size={isCinemaMode ? 36 : 24}
                className="course-rating-confirmed-star"
              />
            ))}
          </div>
          <span className="course-rating-confirmed-text">
            {getScoreLabel(selectedScore || 0)}
          </span>
        </div>
      )}

      {/* Auto-close indicator & progress bar */}
      <div className="course-rating-footer">
        <div className="course-rating-timer-text">
          <Icon name="timer" size={14} />
          <span>{t("courseRating.autoClose", { seconds: remainingSeconds })}</span>
        </div>
        <div className="course-rating-progress-bar">
          <div
            className="course-rating-progress-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
