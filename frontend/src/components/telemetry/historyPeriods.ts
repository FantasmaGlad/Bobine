import type { MetricPoint } from "@/lib/telemetryChart";

export type RangePeriod = "7d" | "30d" | "this_month" | "all";
export type ApiPeriod = "1h" | "6h" | "24h" | RangePeriod;
export type DrawerPeriod = "1h" | "6h" | "24h" | "range";

export const RANGE_LABEL_KEYS: Record<ApiPeriod, string> = {
  "1h": "telemetryDrawer.range1h",
  "6h": "telemetryDrawer.range6h",
  "24h": "telemetryDrawer.range24h",
  "7d": "telemetryDrawer.range7d",
  "30d": "telemetryDrawer.range30d",
  this_month: "telemetryDrawer.rangeMonth",
  all: "telemetryDrawer.rangeAll",
};

const RANGE_SHORT_KEYS: Record<RangePeriod, string> = {
  "7d": "telemetryDrawer.short7d",
  "30d": "telemetryDrawer.short30d",
  this_month: "telemetryDrawer.shortMonth",
  all: "telemetryDrawer.shortAll",
};

const FIXED_SHORT_KEYS = { "1h": "telemetryDrawer.short1h", "6h": "telemetryDrawer.short6h", "24h": "telemetryDrawer.short24h" } as const;

export function periodShortKey(p: DrawerPeriod, rangePeriod: RangePeriod): string {
  return p === "range" ? RANGE_SHORT_KEYS[rangePeriod] : FIXED_SHORT_KEYS[p];
}

export interface HistoryResponse {
  metric: string;
  label: string;
  unit: string;
  period: string;
  points: MetricPoint[];
  current: number;
  min: number;
  max: number;
  avg: number;
  count: number;
}

export function historyTimeFormatter(apiPeriod: ApiPeriod, locale: string) {
  return (isoString: string) => {
    try {
      const d = new Date(isoString);
      if (apiPeriod !== "1h" && apiPeriod !== "6h" && apiPeriod !== "24h") {
        return d.toLocaleDateString(locale, { weekday: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
      }
      return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    } catch {
      return isoString;
    }
  };
}
