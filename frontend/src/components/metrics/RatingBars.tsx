import React from "react";
import StarIcon from "./StarIcon";
import type { RatingBreakdown } from "./types";

export default function RatingBars({ breakdown }: { breakdown: RatingBreakdown[] }) {
  return (
    <div className="metrics-rating-bars">
      {[5, 4, 3, 2, 1].map((star) => {
        const pct = breakdown.find((r) => r.score === star)?.percentage ?? 0;
        return (
          <div key={star} className="metrics-rating-bar-row">
            <span className="metrics-rating-star-num" style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
              {star}
              <StarIcon size={11} />
            </span>
            <div className="metrics-rating-bar-track">
              <div className="metrics-rating-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="metrics-rating-bar-pct">{pct.toFixed(0)}%</span>
          </div>
        );
      })}
    </div>
  );
}
