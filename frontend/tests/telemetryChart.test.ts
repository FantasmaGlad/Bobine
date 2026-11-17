import { test } from "node:test";
import assert from "node:assert/strict";
import { CHART, PLOT_H, PLOT_W, chartGeometry } from "../src/lib/telemetryChart.ts";

test("un pourcentage est borné entre 0 et 100 avec une marge de 5", () => {
  const g = chartGeometry([{ timestamp: "a", value: 2 }, { timestamp: "b", value: 98 }], 2, 98, "%");
  assert.equal(g.yMin, 0);
  assert.equal(g.ySpan, 100);
  assert.equal(g.coords[0].x, CHART.padLeft);
  assert.equal(g.coords[1].x, CHART.padLeft + PLOT_W);
  assert.equal(g.pathD, `M ${g.coords[0].x} ${g.coords[0].y} L ${g.coords[1].x} ${g.coords[1].y}`);
  assert.ok(g.areaD.endsWith(`L ${g.coords[0].x} ${CHART.padTop + PLOT_H} Z`));
});

test("une valeur brute reçoit 10 % de marge et un point seul est centré", () => {
  const g = chartGeometry([{ timestamp: "a", value: 50 }], 40, 60, "°C");
  assert.equal(g.yMin, 38);
  assert.equal(g.ySpan, 24);
  assert.equal(g.coords[0].x, CHART.padLeft + PLOT_W / 2);
});

test("sans point le tracé est vide", () => {
  const g = chartGeometry([], 0, 10, "W");
  assert.deepEqual([g.coords.length, g.pathD, g.areaD], [0, "", ""]);
});
