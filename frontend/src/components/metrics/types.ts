export interface RatingBreakdown {
  score: number;
  count: number;
  percentage: number;
}

export interface CourseStat {
  video_id: number;
  title: string;
  program: string | null;
  thumbnail_path: string | null;
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number;
  total_duration_hours: number;
  average_rating: number | null;
  ratings_count: number;
  sessions_count?: number;
  duration_seconds?: number;
}

export interface HourlyAttendance {
  hour: number;
  sessions: number;
}

export interface DashboardMetrics {
  period: string;
  channel: string;
  kpis: {
    average_satisfaction: number | null;
    ratings_count: number;
    completion_rate: number;
    total_broadcast_hours: number;
    total_sessions: number;
    completed_sessions: number;
  };
  rating_breakdown: RatingBreakdown[];
  hourly_attendance: HourlyAttendance[];
  peak_hours: number[];
  top_courses: CourseStat[];
}
