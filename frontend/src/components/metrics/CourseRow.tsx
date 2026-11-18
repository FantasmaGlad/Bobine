import React from "react";
import Icon from "@/components/Icon";
import StarIcon from "./StarIcon";
import type { CourseStat } from "./types";
import { thumbnailUrl } from "@/lib/thumbnail";


const RANK_CLASS = ["", "rank-1", "rank-2", "rank-3"];

export default function CourseRow({ course, rank }: { course: CourseStat; rank: number }) {
  const thumbSrc = thumbnailUrl(course.thumbnail_path);
  return (
    <tr>
      <td className="metrics-rank-cell">
        <span className={`metrics-rank-badge ${RANK_CLASS[rank] ?? ""}`}>{rank}</span>
      </td>
      <td>
        <div className="metrics-course-cell">
          <div className="metrics-course-thumb">
            {thumbSrc ? (
              <img src={thumbSrc} alt="" className="card-thumbnail" />
            ) : (
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Icon name="movie" size={16} style={{ opacity: 0.25 }} />
              </div>
            )}
          </div>
          <div className="metrics-course-info">
            <span className="metrics-course-title">{course.title}</span>
            <span className="metrics-course-program">{course.program || "Autre"}</span>
          </div>
        </div>
      </td>
      <td style={{ textAlign: "center", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>{course.total_sessions}</td>
      <td>
        <div className="metrics-table-progress-wrap">
          <div className="metrics-table-progress-bar">
            <div className="metrics-table-progress-fill" style={{ width: `${course.completion_rate}%` }} />
          </div>
          <span className="metrics-table-progress-text">{course.completion_rate.toFixed(0)}%</span>
        </div>
      </td>
      <td style={{ textAlign: "right" }}>
        {course.average_rating != null && course.ratings_count > 0 ? (
          <div className="metrics-table-rating">
            <span style={{ color: "var(--accent-text)", display: "inline-flex", alignItems: "center" }}>
              <StarIcon size={13} />
            </span>
            <span>{course.average_rating.toFixed(1)}</span>
            <span className="metrics-table-rating-count">({course.ratings_count})</span>
          </div>
        ) : (
          <span className="metrics-no-rating">—</span>
        )}
      </td>
    </tr>
  );
}
