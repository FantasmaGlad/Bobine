/**
 * Graphe de routage des sorties radio (phase 3) — disposition PURE, déterministe et testable (aucune simulation).
 *
 * Deux colonnes : les SOURCES à gauche (radio câblée, radio réseau, rappels, audio vidéo) et les SORTIES à droite (la
 * sortie par défaut du système, puis chaque sortie audio détectée). Une arête relie une source à la sortie où elle
 * joue. Seules les sources `radio_*` se re-routent (glisser vers une sortie, ou sélection puis validation) : les
 * rappels jouent dans le lecteur de chaque sortie radio, l'audio vidéo reste sur la sortie par défaut du système
 * (le cahier ne route que les sorties radio).
 */
import type { AudioDevice, AudioKind, RadioOutputId, RoutingOutput } from "./devicesApi.ts";

export type SourceKind = "radio" | "announcements" | "video";

export interface GraphSource {
  id: string;
  kind: SourceKind;
  channel: RadioOutputId | null;
  playing: boolean;
  /** Re-routable (glisser / sélection) : seulement les sorties radio. */
  draggable: boolean;
}

export interface GraphSink {
  id: string;
  /** Identifiant de sortie du pilote, `null` pour « sortie par défaut du système ». */
  sinkId: string | null;
  label: string;
  kind: AudioKind | "default";
  /** C'est la sortie par défaut du système. */
  isDefault: boolean;
  /** Sortie mémorisée mais débranchée (fantôme). */
  absent: boolean;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  kind: "route" | "default" | "mix";
  playing: boolean;
  absent: boolean;
}

export interface RoutingGraphModel {
  sources: GraphSource[];
  sinks: GraphSink[];
  edges: GraphEdge[];
}

export const DEFAULT_SINK_ID = "sink:default";

export interface GraphInput {
  outputs: RoutingOutput[];
  devices: AudioDevice[];
  /** Lecture en direct (flux temps réel) qui prime sur celle de la dernière lecture REST. */
  playing?: Partial<Record<RadioOutputId, boolean>>;
  /** Libellé d'une sortie (alias de Bobine compris). */
  displayName: (device: AudioDevice) => string;
  /** Libellé de la sortie par défaut du système. */
  defaultLabel: string;
}

export function sourceId(kind: SourceKind, channel: RadioOutputId | null): string {
  return channel ? `source:${channel}` : `source:${kind}`;
}

export function buildRoutingGraph(input: GraphInput): RoutingGraphModel {
  const visible = input.devices.filter((d) => !d.hidden);
  const defaultDevice = input.devices.find((d) => d.is_default) ?? null;
  const sinks: GraphSink[] = [
    { id: DEFAULT_SINK_ID, sinkId: null, label: input.defaultLabel, kind: "default", isDefault: true, absent: false },
    ...visible
      .filter((d) => d.available)
      .map((d) => ({ id: `sink:${d.id}`, sinkId: d.id, label: input.displayName(d), kind: d.kind, isDefault: d.is_default, absent: false })),
  ];
  const sources: GraphSource[] = [];
  const edges: GraphEdge[] = [];
  const playingOf = (o: RoutingOutput) => input.playing?.[o.channel] ?? o.playing;

  for (const output of input.outputs) {
    const id = sourceId("radio", output.channel);
    const playing = playingOf(output);
    sources.push({ id, kind: "radio", channel: output.channel, playing, draggable: true });
    const route = output.route;
    if (!route) {
      edges.push({ id: `${id}>${DEFAULT_SINK_ID}`, from: id, to: DEFAULT_SINK_ID, kind: "default", playing, absent: false });
    } else if (output.state === "missing") {
      const ghost = `sink:absent:${output.channel}`;
      sinks.push({ id: ghost, sinkId: route.sink_id, label: route.label, kind: route.kind, isDefault: false, absent: true });
      edges.push({ id: `${id}>${ghost}`, from: id, to: ghost, kind: "route", playing: false, absent: true });
    } else {
      // Sortie présente (id courant) ; état « inconnu » : la sortie mémorisée si elle est listée.
      const target = output.sink_id ?? route.sink_id;
      const node = sinks.find((s) => s.sinkId === target);
      const to = node ? node.id : DEFAULT_SINK_ID;
      edges.push({ id: `${id}>${to}`, from: id, to, kind: node ? "route" : "default", playing, absent: false });
    }
  }
  const announcements = sourceId("announcements", null);
  sources.push({ id: announcements, kind: "announcements", channel: null, playing: input.outputs.some((o) => playingOf(o)), draggable: false });
  // Les rappels jouent dans le lecteur de chaque sortie radio : ils suivent la sortie de chacune.
  for (const edge of [...edges]) {
    if (edge.from.startsWith("source:radio_")) {
      edges.push({ id: `${announcements}>${edge.to}#${edge.from}`, from: announcements, to: edge.to, kind: "mix", playing: edge.playing, absent: edge.absent });
    }
  }
  const video = sourceId("video", null);
  sources.push({ id: video, kind: "video", channel: null, playing: false, draggable: false });
  const videoTarget = defaultDevice ? `sink:${defaultDevice.id}` : DEFAULT_SINK_ID;
  edges.push({ id: `${video}>${videoTarget}`, from: video, to: sinks.some((s) => s.id === videoTarget) ? videoTarget : DEFAULT_SINK_ID, kind: "default", playing: false, absent: false });
  return { sources, sinks, edges };
}

export interface PlacedGraphNode {
  id: string;
  side: "source" | "sink";
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PlacedGraphEdge extends GraphEdge {
  d: string;
}

export interface GraphLayout {
  nodes: PlacedGraphNode[];
  edges: PlacedGraphEdge[];
  width: number;
  height: number;
}

export const NODE_WIDTH = 214;
export const NODE_HEIGHT = 54;
const ROW_GAP = 16;
const COLUMN_GAP = 220;
const PADDING = 12;

/** Disposition en deux colonnes, rangées régulières ; la colonne la plus courte est centrée verticalement. */
export function layoutRoutingGraph(model: RoutingGraphModel): GraphLayout {
  const rows = Math.max(model.sources.length, model.sinks.length, 1);
  const columnHeight = (count: number) => count * NODE_HEIGHT + Math.max(0, count - 1) * ROW_GAP;
  const height = columnHeight(rows) + PADDING * 2;
  const width = NODE_WIDTH * 2 + COLUMN_GAP + PADDING * 2;
  const place = (side: "source" | "sink", ids: string[]): PlacedGraphNode[] => {
    const top = PADDING + (columnHeight(rows) - columnHeight(ids.length)) / 2;
    const x = side === "source" ? PADDING : width - PADDING - NODE_WIDTH;
    return ids.map((id, i) => ({ id, side, x, y: top + i * (NODE_HEIGHT + ROW_GAP), width: NODE_WIDTH, height: NODE_HEIGHT }));
  };
  const nodes = [...place("source", model.sources.map((s) => s.id)), ...place("sink", model.sinks.map((s) => s.id))];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edges: PlacedGraphEdge[] = [];
  for (const edge of model.edges) {
    const a = byId.get(edge.from);
    const b = byId.get(edge.to);
    if (!a || !b) continue;
    edges.push({ ...edge, d: edgePath(a.x + a.width, a.y + a.height / 2, b.x, b.y + b.height / 2) });
  }
  return { nodes, edges, width, height };
}

/** Courbe de Bézier horizontale d'une source à une sortie. */
export function edgePath(x1: number, y1: number, x2: number, y2: number): string {
  const dx = Math.max(40, (x2 - x1) / 2);
  return `M${r(x1)} ${r(y1)} C${r(x1 + dx)} ${r(y1)} ${r(x2 - dx)} ${r(y2)} ${r(x2)} ${r(y2)}`;
}
const r = (n: number) => Math.round(n * 10) / 10;

/** Sortie sous le point (coordonnées du graphe) : `null` hors de toute sortie. */
export function sinkAt(layout: GraphLayout, point: { x: number; y: number }): string | null {
  const hit = layout.nodes.find((n) => n.side === "sink" && point.x >= n.x && point.x <= n.x + n.width && point.y >= n.y && point.y <= n.y + n.height);
  return hit ? hit.id : null;
}

export interface Assignment {
  channel: RadioOutputId;
  /** `null` = retour à la sortie par défaut (efface la route). */
  sinkId: string | null;
}

/**
 * Re-routage demandé par un dépôt (ou une sélection validée) : seule une source radio peut être déposée, et
 * seulement sur une sortie réelle ou sur la sortie par défaut ; une sortie fantôme (débranchée) ne reçoit rien.
 */
export function assignmentFor(model: RoutingGraphModel, sourceNodeId: string, sinkNodeId: string): Assignment | null {
  const source = model.sources.find((s) => s.id === sourceNodeId);
  const sink = model.sinks.find((s) => s.id === sinkNodeId);
  if (!source?.draggable || !source.channel || !sink || sink.absent) return null;
  return { channel: source.channel, sinkId: sink.sinkId };
}

/** Texte tronqué à `max` caractères avec « … » (les libellés SVG ne se replient pas). */
export function truncateLabel(text: string, max = 26): string {
  return text.length > max ? `${text.slice(0, Math.max(1, max - 1)).trimEnd()}…` : text;
}
