export interface MetricPoint {
  timestamp: string;
  value: number;
}

export const CHART = { width: 460, height: 220, padLeft: 46, padRight: 20, padTop: 24, padBottom: 32 } as const;
export const PLOT_W = CHART.width - CHART.padLeft - CHART.padRight;
export const PLOT_H = CHART.height - CHART.padTop - CHART.padBottom;

export interface ChartCoord {
  x: number;
  y: number;
  pt: MetricPoint;
}

export interface ChartGeometry {
  yMin: number;
  ySpan: number;
  coords: ChartCoord[];
  pathD: string;
  areaD: string;
}

function yBounds(points: MetricPoint[], minVal: number, maxVal: number, unit: string): [number, number] {
  let yMin = Math.floor(Math.min(...(points.length ? points.map((p) => p.value) : [0]), minVal));
  let yMax = Math.ceil(Math.max(...(points.length ? points.map((p) => p.value) : [100]), maxVal));
  if (unit === "%") {
    yMin = Math.max(0, yMin - 5);
    yMax = Math.min(100, Math.max(10, yMax + 5));
  } else {
    const range = Math.max(1, yMax - yMin);
    yMin = Math.max(0, Math.floor(yMin - range * 0.1));
    yMax = Math.ceil(yMax + range * 0.1);
  }
  return [yMin, yMax];
}

export function chartGeometry(points: MetricPoint[], minVal: number, maxVal: number, unit: string): ChartGeometry {
  const [yMin, yMax] = yBounds(points, minVal, maxVal, unit);
  const ySpan = Math.max(1, yMax - yMin);
  const coords = points.map((pt, idx) => {
    const x = CHART.padLeft + (points.length > 1 ? (idx / (points.length - 1)) * PLOT_W : PLOT_W / 2);
    const y = CHART.padTop + PLOT_H - ((pt.value - yMin) / ySpan) * PLOT_H;
    return { x, y, pt };
  });
  if (coords.length === 0) return { yMin, ySpan, coords, pathD: "", areaD: "" };
  const pathD = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  const bottomY = CHART.padTop + PLOT_H;
  const areaD = `${pathD} L ${coords[coords.length - 1].x} ${bottomY} L ${coords[0].x} ${bottomY} Z`;
  return { yMin, ySpan, coords, pathD, areaD };
}
