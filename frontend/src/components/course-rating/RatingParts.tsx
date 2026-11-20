import Icon from "@/components/Icon";

type T = (key: string, params?: Record<string, string | number>) => string;

const STARS = [1, 2, 3, 4, 5];

export function scoreLabel(score: number, t: T): string {
  return score >= 1 && score <= 5 && Number.isInteger(score) ? t(`courseRating.rating${score}`) : "";
}

interface HeaderProps {
  submitted: boolean;
  courseTitle: string;
  isCinemaMode: boolean;
  onClose?: () => void;
  t: T;
}

export function RatingHeader({ submitted, courseTitle, isCinemaMode, onClose, t }: HeaderProps) {
  const subtitle = courseTitle ? (submitted ? courseTitle : `${courseTitle} — ${t("courseRating.subtitle")}`) : t("courseRating.subtitle");
  return (
    <div className="course-rating-header">
      <div className="course-rating-title-block">
        <h4 className="course-rating-title">
          {submitted ? t("courseRating.submitSuccess") : t("courseRating.title")}
        </h4>
        <p className="course-rating-subtitle">{subtitle}</p>
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
  );
}

interface StarsProps {
  active: number;
  isCinemaMode: boolean;
  onHover: (score: number | null) => void;
  onSelect: (score: number) => void;
  t: T;
}

export function RatingStars({ active, isCinemaMode, onHover, onSelect, t }: StarsProps) {
  return (
    <div className="course-rating-stars-row">
      <div className="course-rating-stars-list">
        {STARS.map((star) => {
          const isFilled = star <= active;
          return (
            <button
              key={star}
              type="button"
              className={`course-rating-star-btn ${isFilled ? "active" : ""}`}
              onMouseEnter={() => onHover(star)}
              onMouseLeave={() => onHover(null)}
              onClick={() => onSelect(star)}
              aria-label={`${star} / 5 - ${scoreLabel(star, t)}`}
            >
              <Icon name={isFilled ? "star" : "star_outline"} size={isCinemaMode ? 48 : 32} className="course-rating-star-icon" />
            </button>
          );
        })}
      </div>
      <div className="course-rating-score-label">
        {active > 0 ? scoreLabel(active, t) : " "}
      </div>
    </div>
  );
}

export function RatingConfirmed({ score, isCinemaMode, t }: { score: number; isCinemaMode: boolean; t: T }) {
  return (
    <div className="course-rating-submitted-feedback">
      <div className="course-rating-confirmed-stars">
        {STARS.map((star) => (
          <Icon key={star} name={star <= score ? "star" : "star_outline"} size={isCinemaMode ? 36 : 24} className="course-rating-confirmed-star" />
        ))}
      </div>
      <span className="course-rating-confirmed-text">{scoreLabel(score, t)}</span>
    </div>
  );
}

export function RatingProgress({ percent }: { percent: number }) {
  return (
    <div className="course-rating-footer">
      <div className="course-rating-progress-bar">
        <div className="course-rating-progress-fill" style={{ transform: `scaleX(${percent / 100})` }} />
      </div>
    </div>
  );
}
