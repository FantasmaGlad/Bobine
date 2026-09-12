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
  autoCloseSeconds = 20,
  onClose,
  onRated,
  isCinemaMode = false,
}: CourseRatingWidgetProps) {
  const { t } = useAppSettings();
  const [selectedScore, setSelectedScore] = useState<number | null>(null);
  const [hoveredScore, setHoveredScore] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);

  // Durée effective du compte à rebours (calée sur la transition entre cours)
  const duration = autoCloseSeconds > 0 ? autoCloseSeconds : 20;
  const [remainingSeconds, setRemainingSeconds] = useState(duration);
  const startTimeRef = useRef<number>(Date.now());
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  // Compte à rebours précis basé sur l'horloge système (immune aux saccades et re-renders)
  useEffect(() => {
    if (submitted) return; // Si déjà soumis, le timer post-soumission prend le relais
    setRemainingSeconds(duration);
    startTimeRef.current = Date.now();

    const timer = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      const left = Math.max(0, duration - elapsed);
      setRemainingSeconds(left);
      if (left <= 0) {
        clearInterval(timer);
        if (onCloseRef.current) onCloseRef.current();
      }
    }, 100);

    return () => clearInterval(timer);
  }, [duration, submitted]);

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
            rating: score,
            channel,
            source: isCinemaMode ? "cinema" : "grid",
          }),
        });
      } catch (err) {
        console.error("Failed to submit rating:", err);
      }

      if (onRated) onRated(score);

      // Fermeture automatique après affichage du remerciement (2,5s)
      setTimeout(() => {
        if (onCloseRef.current) onCloseRef.current();
      }, 2500);
    },
    [videoId, channel, isCinemaMode, submitted, onRated]
  );

  // Navigation clavier / télécommande
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (onCloseRef.current) onCloseRef.current();
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
  }, [hoveredScore, submitted, handleSelectScore]);

  const currentActiveScore = hoveredScore || selectedScore || 0;
  // Progression inversée : commence à 100% et descend progressivement à 0%
  const progressPercent = Math.max(0, Math.min(100, (remainingSeconds / duration) * 100));

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
            {submitted ? t("courseRating.submitSuccess") : t("courseRating.title")}
          </h4>
          <p className="course-rating-subtitle">
            {courseTitle ? (submitted ? courseTitle : `${courseTitle} — ${t("courseRating.subtitle")}`) : t("courseRating.subtitle")}
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

      {/* Barre de progression inversée (sans texte "Fermeture dans 300 s") */}
      {!submitted && (
        <div className="course-rating-footer">
          <div className="course-rating-progress-bar">
            <div
              className="course-rating-progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
