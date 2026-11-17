"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import CourseRow from "./CourseRow";
import type { CourseStat } from "./types";

export default function CourseRanking({ courses }: { courses: CourseStat[] }) {
  const { t } = useAppSettings();
  return (
    <section className="metrics-section-card">
      <div className="metrics-section-header">
        <div>
          <h3>
            <Icon name="leaderboard" size={20} /> {t("metricsPage.rankingTitle")}
          </h3>
          <p className="metrics-section-subtitle">{t("metricsPage.rankingSubtitle")}</p>
        </div>
      </div>
      {courses.length > 0 ? (
        <div className="metrics-table-wrapper">
          <table className="metrics-table">
            <thead>
              <tr>
                <th style={{ width: "48px" }}>{t("metricsPage.thRank")}</th>
                <th>{t("metricsPage.thCourse")}</th>
                <th style={{ textAlign: "center" }}>{t("metricsPage.thSessions")}</th>
                <th style={{ textAlign: "center" }}>{t("metricsPage.thCompletion")}</th>
                <th style={{ textAlign: "right" }}>{t("metricsPage.thRating")}</th>
              </tr>
            </thead>
            <tbody>
              {courses.map((course, idx) => <CourseRow key={course.video_id} course={course} rank={idx + 1} />)}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="metrics-empty">
          <p>{t("metricsPage.emptyCourses")}</p>
        </div>
      )}
    </section>
  );
}
