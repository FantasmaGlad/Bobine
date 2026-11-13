export interface Announcement {
  id: number;
  description: string;
  duration_seconds: number | null;
  enabled: boolean;
}

export type RuleType = "every_n_tracks" | "every_x_minutes" | "fixed_times";

export type RuleTarget = "radio_cable" | "radio_network" | "both";

export interface Rule {
  id: number;
  rule_type: RuleType;
  n_tracks: number | null;
  interval_minutes: number | null;
  times_of_day: string[] | null;
  enabled: boolean;
  target: RuleTarget;
}
