/**
 * Carte des périphériques en « système solaire » — disposition PURE (testable, `frontend/tests/`).
 * La machine est au centre ; trois orbites : réseau (Wi-Fi, Ethernet), appareils (sorties audio, Bluetooth),
 * écrans et télécommandes Bobine. La disposition est calculée UNE fois, de façon déterministe : pas de
 * simulation physique, aucun coût de rendu au-delà du SVG.
 */

export type NodeKind = "machine" | "audio" | "bluetooth" | "wifi" | "ethernet" | "screen" | "remote";
export type LinkMedium = "wifi" | "bluetooth" | "wired" | "internal" | "lan";

export interface TopoNode {
  id: string;
  kind: NodeKind;
  label: string;
  sub: string;
  state: "active" | "idle" | "off";
  ring: number;
  tab: "audio" | "bluetooth" | "wifi" | null;
  ref: string | null;
  meta: Record<string, unknown>;
}

export interface TopoLink {
  id: string;
  from: string;
  to: string;
  medium: LinkMedium;
  state: "active" | "idle" | "off";
  quality: number | null;
}

export interface Topology {
  nodes: TopoNode[];
  links: TopoLink[];
  counts: { audio: number; bluetooth: number; screens: number };
}

export interface PlacedNode extends TopoNode {
  x: number;
  y: number;
  /** Rayon du disque du nœud. */
  r: number;
  /** Angle (radians) autour du centre. */
  angle: number;
}

export interface PlacedLink extends TopoLink {
  a: { x: number; y: number };
  b: { x: number; y: number };
}

export interface MapLayout {
  nodes: PlacedNode[];
  links: PlacedLink[];
  /** Rayons des orbites à dessiner. */
  rings: number[];
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
}

export const RING_RADII = [0, 175, 305, 430];
const NODE_RADIUS: Record<NodeKind, number> = { machine: 46, audio: 30, bluetooth: 30, wifi: 34, ethernet: 34, screen: 30, remote: 28 };
const TAU = Math.PI * 2;

/** Hash déterministe (FNV-1a) → [0, 1[ : variation stable d'un chargement à l'autre. */
export function hash01(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return ((h >>> 0) % 100000) / 100000;
}

const place = (radius: number, angle: number) => ({ x: Math.round(Math.cos(angle) * radius * 10) / 10, y: Math.round(Math.sin(angle) * radius * 10) / 10 });

/** Dispose les nœuds d'une orbite à intervalles réguliers, avec une légère variation déterministe. */
function ringAngles(ids: string[], start: number): Map<string, number> {
  const angles = new Map<string, number>();
  const step = TAU / Math.max(ids.length, 1);
  ids.forEach((id, i) => {
    const jitter = (hash01(id) - 0.5) * step * 0.18;
    angles.set(id, start + i * step + jitter);
  });
  return angles;
}

/** Écarte, sans hasard, les nœuds de l'orbite externe qui se chevauchent : quelques passes d'ajustement angulaire. */
function relaxOuter(outer: PlacedNode[]): void {
  const MIN_GAP = 10;
  const radiusOf = (n: PlacedNode) => Math.hypot(n.x, n.y);
  const signedDiff = (from: number, to: number) => {
    let d = (to - from) % TAU;
    if (d > Math.PI) d -= TAU;
    if (d <= -Math.PI) d += TAU;
    return d;
  };
  for (let pass = 0; pass < 120; pass++) {
    let moved = false;
    for (let i = 0; i < outer.length; i++) {
      for (let j = i + 1; j < outer.length; j++) {
        const a = outer[i];
        const b = outer[j];
        const gap = Math.hypot(a.x - b.x, a.y - b.y) - a.r - b.r;
        if (gap >= MIN_GAP) continue;
        const delta = (MIN_GAP - gap) / Math.max(radiusOf(a), radiusOf(b)) / 2 + 0.002;
        const direction = signedDiff(a.angle, b.angle) >= 0 ? 1 : -1;
        a.angle -= delta * direction;
        b.angle += delta * direction;
        Object.assign(a, place(radiusOf(a), a.angle));
        Object.assign(b, place(radiusOf(b), b.angle));
        moved = true;
      }
    }
    if (!moved) break;
  }
}

export function layoutOrbits(topology: Topology): MapLayout {
  const placed = new Map<string, PlacedNode>();
  const base = (n: TopoNode): PlacedNode => ({ ...n, x: 0, y: 0, r: NODE_RADIUS[n.kind], angle: 0 });
  const byRing = (ring: number) => topology.nodes.filter((n) => n.ring === ring);
  const anchorOf = new Map(topology.links.map((l) => [l.to, l.from]));

  const machine = topology.nodes.find((n) => n.ring === 0);
  if (machine) placed.set(machine.id, base(machine));

  // Orbite 1 (réseau) et orbite 2 (appareils) : réparties régulièrement, décalées entre elles.
  for (const [ring, start] of [[1, -Math.PI / 2], [2, -Math.PI / 2 + 0.35]] as const) {
    const nodes = byRing(ring);
    const angles = ringAngles(nodes.map((n) => n.id), start);
    for (const n of nodes) {
      const angle = angles.get(n.id) ?? 0;
      placed.set(n.id, { ...base(n), ...place(RING_RADII[ring], angle), angle });
    }
  }

  // Orbite 3 (écrans et télécommandes) : groupés autour du nœud réseau auquel ils sont rattachés.
  const outer = byRing(3);
  const groups = new Map<string, TopoNode[]>();
  for (const n of outer) {
    const anchor = anchorOf.get(n.id) ?? "machine";
    groups.set(anchor, [...(groups.get(anchor) ?? []), n]);
  }
  const free: TopoNode[] = [];
  let index = 0;
  for (const [anchor, members] of groups) {
    const anchorNode = placed.get(anchor);
    if (anchor === "machine" || !anchorNode) {
      free.push(...members);
      continue;
    }
    const spread = 0.26;
    members.forEach((n, i) => {
      const angle = anchorNode.angle + (i - (members.length - 1) / 2) * spread;
      const radius = RING_RADII[3] + (index++ % 3) * 70;
      placed.set(n.id, { ...base(n), ...place(radius, angle), angle });
    });
  }
  const freeAngles = ringAngles(free.map((n) => n.id), Math.PI / 2 + 0.2);
  free.forEach((n, i) => {
    const angle = freeAngles.get(n.id) ?? 0;
    placed.set(n.id, { ...base(n), ...place(RING_RADII[3] + (i % 3) * 70, angle), angle });
  });

  relaxOuter([...placed.values()].filter((n) => n.ring === 3));

  const nodes = topology.nodes.map((n) => placed.get(n.id)).filter((n): n is PlacedNode => Boolean(n));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links: PlacedLink[] = topology.links
    .filter((l) => byId.has(l.from) && byId.has(l.to))
    .map((l) => ({ ...l, a: { x: byId.get(l.from)!.x, y: byId.get(l.from)!.y }, b: { x: byId.get(l.to)!.x, y: byId.get(l.to)!.y } }));

  const rings = [1, 2, 3].filter((r) => byRing(r).length > 0).map((r) => RING_RADII[r]);
  const xs = nodes.flatMap((n) => [n.x - n.r - 40, n.x + n.r + 40]);
  const ys = nodes.flatMap((n) => [n.y - n.r - 40, n.y + n.r + 40]);
  const bounds = nodes.length
    ? { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) }
    : { minX: -200, minY: -200, maxX: 200, maxY: 200 };
  return { nodes, links, rings, bounds };
}

/** Style d'un trait : Wi-Fi en pointillés longs, Bluetooth en pointillés courts, filaire en trait plein. */
export function linkStyle(medium: LinkMedium): { dash: string; width: number; cap: "butt" | "round" } {
  switch (medium) {
    case "wifi": return { dash: "16 10", width: 2.4, cap: "butt" };
    case "bluetooth": return { dash: "3 7", width: 2.8, cap: "round" };
    case "wired": return { dash: "", width: 3, cap: "butt" };
    case "internal": return { dash: "", width: 1.8, cap: "butt" };
    default: return { dash: "1 9", width: 2.4, cap: "round" }; // lan : liaison dont le moyen n'est pas connu
  }
}

/** Courbe légère (quadratique) entre deux points, pour éviter que les traits se superposent exactement. */
export function curvePath(a: { x: number; y: number }, b: { x: number; y: number }, bend = 0.1): string {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const cx = mx - (b.y - a.y) * bend;
  const cy = my + (b.x - a.x) * bend;
  return `M ${a.x} ${a.y} Q ${Math.round(cx * 10) / 10} ${Math.round(cy * 10) / 10} ${b.x} ${b.y}`;
}

/** Nœud et voisins directs : ce qui reste en évidence au survol, le reste est atténué. */
export function neighborhood(links: TopoLink[], id: string): { nodes: Set<string>; links: Set<string> } {
  const nodes = new Set<string>([id]);
  const linkIds = new Set<string>();
  for (const l of links) {
    if (l.from === id || l.to === id) {
      nodes.add(l.from);
      nodes.add(l.to);
      linkIds.add(l.id);
    }
  }
  return { nodes, links: linkIds };
}

export const ZOOM_MIN = 0.45;
export const ZOOM_MAX = 2.8;

export const clampZoom = (z: number): number => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));

/** Vue qui fait tenir tous les nœuds dans un cadre de la taille donnée. */
export function fitView(bounds: MapLayout["bounds"], size: { width: number; height: number }): { scale: number; tx: number; ty: number } {
  const w = Math.max(1, bounds.maxX - bounds.minX);
  const h = Math.max(1, bounds.maxY - bounds.minY);
  const scale = clampZoom(Math.min(size.width / w, size.height / h));
  return { scale, tx: size.width / 2 - ((bounds.minX + bounds.maxX) / 2) * scale, ty: size.height / 2 - ((bounds.minY + bounds.maxY) / 2) * scale };
}

/** Zoom autour d'un point de l'écran : le point reste fixe sous le curseur ou les doigts. */
export function zoomAt(view: { scale: number; tx: number; ty: number }, point: { x: number; y: number }, factor: number): { scale: number; tx: number; ty: number } {
  const scale = clampZoom(view.scale * factor);
  const k = scale / view.scale;
  return { scale, tx: point.x - (point.x - view.tx) * k, ty: point.y - (point.y - view.ty) * k };
}

export function nodeIcon(node: Pick<TopoNode, "kind" | "meta">): string {
  switch (node.kind) {
    case "machine": return "dns";
    case "wifi": return "wifi";
    case "ethernet": return "lan";
    case "bluetooth": return "bluetooth";
    case "remote": return "settings_remote";
    case "screen": return node.meta.page === "radio" ? "radio" : "tv";
    case "audio": {
      const kind = node.meta.device_kind;
      return kind === "hdmi" ? "settings_input_hdmi" : kind === "usb" ? "usb" : kind === "jack" ? "headphones" : "speaker";
    }
  }
}
