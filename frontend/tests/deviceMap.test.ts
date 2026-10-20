import { test } from "node:test";
import assert from "node:assert/strict";
import {
  clampZoom, curvePath, fitView, hash01, layoutOrbits, linkStyle, neighborhood, RING_RADII, zoomAt, ZOOM_MAX, ZOOM_MIN,
  type TopoLink, type TopoNode, type Topology,
} from "../src/lib/deviceMap.ts";

const node = (id: string, kind: TopoNode["kind"], ring: number, meta: Record<string, unknown> = {}): TopoNode => ({
  id, kind, label: id, sub: "", state: "active", ring, tab: null, ref: null, meta,
});
const link = (from: string, to: string, medium: TopoLink["medium"]): TopoLink => ({ id: `${from}>${to}`, from, to, medium, state: "active", quality: null });

function sample(extra = 0): Topology {
  const nodes = [
    node("machine", "machine", 0), node("wifi", "wifi", 1), node("eth", "ethernet", 1),
    node("audio:a", "audio", 2), node("audio:b", "audio", 2, { device_kind: "hdmi" }), node("bt:1", "bluetooth", 2),
    node("c:1", "screen", 3, { page: "cinema" }), node("c:2", "remote", 3), node("c:3", "screen", 3, { page: "radio" }),
  ];
  const links = [
    link("machine", "wifi", "wifi"), link("machine", "eth", "wired"), link("machine", "audio:a", "internal"), link("machine", "audio:b", "wired"),
    link("machine", "bt:1", "bluetooth"), link("wifi", "c:1", "wifi"), link("wifi", "c:2", "wifi"), link("machine", "c:3", "lan"),
  ];
  for (let i = 0; i < extra; i++) {
    nodes.push(node(`x:${i}`, "screen", 3));
    links.push(link("machine", `x:${i}`, "lan"));
  }
  return { nodes, links, counts: { audio: 2, bluetooth: 1, screens: 3 } };
}

test("la disposition est déterministe et place la machine au centre", () => {
  const a = layoutOrbits(sample());
  const b = layoutOrbits(sample());
  assert.deepEqual(a.nodes.map((n) => [n.id, n.x, n.y]), b.nodes.map((n) => [n.id, n.x, n.y]));
  const machine = a.nodes.find((n) => n.id === "machine")!;
  assert.deepEqual([machine.x, machine.y], [0, 0]);
  assert.deepEqual(a.rings, [RING_RADII[1], RING_RADII[2], RING_RADII[3]]);
});

test("chaque orbite a le bon rayon (hors orbite externe alternée) et aucun nœud ne se chevauche", () => {
  for (const extra of [0, 12, 30]) {
    const layout = layoutOrbits(sample(extra));
    const dist = (n: { x: number; y: number }) => Math.hypot(n.x, n.y);
    for (const n of layout.nodes.filter((n) => n.ring === 1)) assert.ok(Math.abs(dist(n) - RING_RADII[1]) < 1, n.id);
    for (const n of layout.nodes.filter((n) => n.ring === 2)) assert.ok(Math.abs(dist(n) - RING_RADII[2]) < 1, n.id);
    const nodes = layout.nodes;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const gap = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y) - nodes[i].r - nodes[j].r;
        assert.ok(gap > -1, `${nodes[i].id} chevauche ${nodes[j].id} (extra=${extra}, écart ${gap.toFixed(1)})`);
      }
    }
  }
});

test("les écrans rattachés au Wi-Fi se placent près de leur point d'accès", () => {
  const layout = layoutOrbits(sample());
  const wifi = layout.nodes.find((n) => n.id === "wifi")!;
  for (const id of ["c:1", "c:2"]) {
    const n = layout.nodes.find((x) => x.id === id)!;
    let delta = Math.abs(n.angle - wifi.angle) % (Math.PI * 2);
    delta = Math.min(delta, Math.PI * 2 - delta);
    assert.ok(delta < 0.5, `${id} trop loin de son point d'accès (${delta.toFixed(2)} rad)`);
  }
});

test("tout nœud est dans les bornes et chaque lien a ses deux extrémités", () => {
  const layout = layoutOrbits(sample(6));
  for (const n of layout.nodes) {
    assert.ok(n.x - n.r >= layout.bounds.minX && n.x + n.r <= layout.bounds.maxX);
    assert.ok(n.y - n.r >= layout.bounds.minY && n.y + n.r <= layout.bounds.maxY);
  }
  assert.equal(layout.links.length, layoutOrbits(sample(6)).links.length);
  const empty = layoutOrbits({ nodes: [], links: [], counts: { audio: 0, bluetooth: 0, screens: 0 } });
  assert.deepEqual([empty.nodes.length, empty.rings.length], [0, 0]);
});

test("styles de trait : Wi-Fi long, Bluetooth court, filaire plein", () => {
  const wifi = linkStyle("wifi").dash.split(" ").map(Number);
  const bt = linkStyle("bluetooth").dash.split(" ").map(Number);
  assert.ok(wifi[0] > bt[0] * 3, "les pointillés Wi-Fi sont nettement plus longs");
  assert.equal(linkStyle("wired").dash, "");
  assert.equal(linkStyle("internal").dash, "");
  assert.notEqual(linkStyle("lan").dash, linkStyle("wifi").dash);
});

test("voisinage au survol", () => {
  const { links } = sample();
  const near = neighborhood(links, "wifi");
  assert.deepEqual([...near.nodes].sort(), ["c:1", "c:2", "machine", "wifi"]);
  assert.equal(near.links.size, 3);
});

test("zoom borné, centré sur le point, et vue qui fait tout tenir", () => {
  assert.equal(clampZoom(0.01), ZOOM_MIN);
  assert.equal(clampZoom(99), ZOOM_MAX);
  const view = { scale: 1, tx: 0, ty: 0 };
  const zoomed = zoomAt(view, { x: 100, y: 50 }, 2);
  assert.equal(zoomed.scale, 2);
  // le point sous le curseur ne bouge pas : (100 - tx) / scale reste constant
  assert.equal((100 - zoomed.tx) / zoomed.scale, 100);
  assert.equal((50 - zoomed.ty) / zoomed.scale, 50);
  const fit = fitView({ minX: -500, minY: -250, maxX: 500, maxY: 250 }, { width: 1000, height: 400 });
  assert.ok(fit.scale <= 1 && fit.scale >= ZOOM_MIN);
  assert.ok(Math.abs(fit.tx - 500) < 1e-6);
});

test("hash stable et courbe valide", () => {
  assert.equal(hash01("abc"), hash01("abc"));
  assert.ok(hash01("abc") !== hash01("abd"));
  assert.match(curvePath({ x: 0, y: 0 }, { x: 100, y: 0 }), /^M 0 0 Q [-\d.]+ [-\d.]+ 100 0$/);
});
