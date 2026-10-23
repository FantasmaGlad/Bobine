import { test } from "node:test";
import assert from "node:assert/strict";
import {
  assignmentFor, buildRoutingGraph, DEFAULT_SINK_ID, edgePath, layoutRoutingGraph, NODE_HEIGHT, NODE_WIDTH, sinkAt, truncateLabel,
  type GraphInput,
} from "../src/lib/routingGraph.ts";
import { outputLabelsHidden, summarizeRouting, type AudioDevice, type RoutingOutput, type RoutingPlayer } from "../src/lib/devicesApi.ts";

const device = (id: string, patch: Partial<AudioDevice> = {}): AudioDevice => ({
  id, name: id.toUpperCase(), kind: "internal", is_default: false, volume: 1, muted: false, available: true, ...patch,
});
const SPEAKER = device("speaker", { is_default: true });
const JBL = device("jbl", { kind: "bluetooth" });
const HDMI = device("hdmi", { kind: "hdmi" });

const output = (channel: RoutingOutput["channel"], patch: Partial<RoutingOutput> = {}): RoutingOutput => ({
  channel, route: null, state: "default", sink_id: null, playing: false, players: [], server: null, ...patch,
});
const route = (sink: AudioDevice, fallback: "default" | "mute" = "default") => ({ sink_id: sink.id, key: `node:${sink.id}`, label: sink.name, kind: sink.kind, fallback });

function input(patch: Partial<GraphInput> = {}): GraphInput {
  return {
    outputs: [output("radio_cable"), output("radio_network")],
    devices: [SPEAKER, JBL, HDMI],
    displayName: (d) => d.alias?.trim() || d.name,
    defaultLabel: "Sortie par défaut",
    ...patch,
  };
}

test("sans route : les deux radios jouent sur la sortie par défaut, rappels et vidéo suivent", () => {
  const model = buildRoutingGraph(input());
  assert.deepEqual(model.sources.map((s) => s.id), ["source:radio_cable", "source:radio_network", "source:announcements", "source:video"]);
  assert.deepEqual(model.sinks.map((s) => s.id), [DEFAULT_SINK_ID, "sink:speaker", "sink:jbl", "sink:hdmi"]);
  const route = (id: string) => model.edges.find((e) => e.id === id);
  assert.equal(route(`source:radio_cable>${DEFAULT_SINK_ID}`)?.kind, "default");
  assert.equal(route(`source:radio_network>${DEFAULT_SINK_ID}`)?.kind, "default");
  assert.equal(model.edges.filter((e) => e.kind === "mix").length, 2); // les rappels suivent chaque sortie radio
  assert.equal(route("source:video>sink:speaker")?.kind, "default"); // l'audio vidéo reste sur la sortie par défaut du système
});

test("route vers une sortie présente : arête propre ; seules les radios se re-routent", () => {
  const model = buildRoutingGraph(input({ outputs: [output("radio_cable", { route: route(JBL), state: "routed", sink_id: "jbl", playing: true }), output("radio_network")] }));
  const edge = model.edges.find((e) => e.from === "source:radio_cable");
  assert.deepEqual([edge?.to, edge?.kind, edge?.playing], ["sink:jbl", "route", true]);
  assert.ok(model.edges.some((e) => e.kind === "mix" && e.to === "sink:jbl"));
  assert.deepEqual(model.sources.map((s) => s.draggable), [true, true, false, false]);
});

test("sortie mémorisée débranchée : nœud fantôme relié en pointillé, jamais déposable", () => {
  const model = buildRoutingGraph(input({ devices: [SPEAKER, HDMI], outputs: [output("radio_cable", { route: route(JBL), state: "missing" }), output("radio_network")] }));
  const ghost = model.sinks.find((s) => s.absent);
  assert.ok(ghost && ghost.label === "JBL");
  assert.equal(model.edges.find((e) => e.to === ghost.id)?.absent, true);
  assert.equal(assignmentFor(model, "source:radio_network", ghost.id), null);
});

test("lecture en direct prioritaire sur la dernière lecture REST ; sorties masquées et débranchées absentes", () => {
  const model = buildRoutingGraph(input({
    devices: [SPEAKER, { ...JBL, hidden: true }, { ...HDMI, available: false }],
    outputs: [output("radio_cable", { playing: false }), output("radio_network", { playing: true })],
    playing: { radio_cable: true, radio_network: false },
  }));
  assert.deepEqual(model.sinks.map((s) => s.id), [DEFAULT_SINK_ID, "sink:speaker"]);
  assert.deepEqual(model.sources.filter((s) => s.kind === "radio").map((s) => s.playing), [true, false]);
});

test("liste des sorties indisponible : seule la sortie par défaut reste, aucune exception", () => {
  const model = buildRoutingGraph(input({ devices: [] }));
  assert.deepEqual(model.sinks.map((s) => s.id), [DEFAULT_SINK_ID]);
  assert.ok(model.edges.every((e) => e.to === DEFAULT_SINK_ID));
});

test("alias de Bobine utilisé pour le libellé des sorties", () => {
  const model = buildRoutingGraph(input({ devices: [{ ...SPEAKER, alias: "Salle 1" }] }));
  assert.equal(model.sinks[1].label, "Salle 1");
});

test("disposition : deux colonnes déterministes, nœuds sans chevauchement, arêtes entre bords", () => {
  const model = buildRoutingGraph(input());
  const a = layoutRoutingGraph(model);
  const b = layoutRoutingGraph(buildRoutingGraph(input()));
  assert.deepEqual(a, b);
  const sources = a.nodes.filter((n) => n.side === "source");
  const sinks = a.nodes.filter((n) => n.side === "sink");
  assert.ok(sources.every((n) => n.x === sources[0].x) && sinks.every((n) => n.x === sinks[0].x));
  assert.ok(sinks[0].x - (sources[0].x + NODE_WIDTH) > 100);
  for (const column of [sources, sinks]) {
    for (let i = 1; i < column.length; i++) assert.ok(column[i].y >= column[i - 1].y + NODE_HEIGHT, "chevauchement");
  }
  assert.ok(a.nodes.every((n) => n.x >= 0 && n.y >= 0 && n.x + n.width <= a.width && n.y + n.height <= a.height));
  assert.equal(a.edges.length, model.edges.length);
  const first = a.edges[0];
  const from = a.nodes.find((n) => n.id === first.from)!;
  assert.ok(first.d.startsWith(`M${from.x + from.width} ${from.y + NODE_HEIGHT / 2} C`));
});

test("la colonne la plus courte est centrée verticalement", () => {
  const layout = layoutRoutingGraph(buildRoutingGraph(input({ devices: [] }))); // 4 sources, 1 sortie
  const sink = layout.nodes.find((n) => n.side === "sink")!;
  const sources = layout.nodes.filter((n) => n.side === "source");
  const centre = (sources[0].y + sources[sources.length - 1].y + NODE_HEIGHT) / 2;
  assert.ok(Math.abs(sink.y + NODE_HEIGHT / 2 - centre) < 0.5);
});

test("sortie sous le pointeur : seules les sorties comptent", () => {
  const layout = layoutRoutingGraph(buildRoutingGraph(input()));
  const sink = layout.nodes.find((n) => n.id === "sink:jbl")!;
  const source = layout.nodes.find((n) => n.id === "source:radio_cable")!;
  assert.equal(sinkAt(layout, { x: sink.x + 5, y: sink.y + 5 }), "sink:jbl");
  assert.equal(sinkAt(layout, { x: source.x + 5, y: source.y + 5 }), null);
  assert.equal(sinkAt(layout, { x: -50, y: -50 }), null);
});

test("re-routage : radio vers une sortie ou vers la sortie par défaut ; rappels et vidéo ne se déposent pas", () => {
  const model = buildRoutingGraph(input());
  assert.deepEqual(assignmentFor(model, "source:radio_cable", "sink:jbl"), { channel: "radio_cable", sinkId: "jbl" });
  assert.deepEqual(assignmentFor(model, "source:radio_network", DEFAULT_SINK_ID), { channel: "radio_network", sinkId: null });
  assert.equal(assignmentFor(model, "source:announcements", "sink:jbl"), null);
  assert.equal(assignmentFor(model, "source:video", "sink:jbl"), null);
  assert.equal(assignmentFor(model, "source:radio_cable", "inconnu"), null);
  assert.equal(assignmentFor(model, "inconnu", "sink:jbl"), null);
});

test("tracé et libellés", () => {
  assert.equal(edgePath(0, 0, 100, 0), "M0 0 C50 0 50 0 100 0");
  assert.equal(truncateLabel("court"), "court");
  assert.equal(truncateLabel("x".repeat(40), 10), `${"x".repeat(9)}…`);
});

// --- résumé d'une route -------------------------------------------------------

const player = (status: string | null, local = true, primary = true): RoutingPlayer => ({ local, primary, status });

test("résumé : aucune route, sortie absente (repli), lecteur absent", () => {
  assert.deepEqual(summarizeRouting(output("radio_cable")), { tone: "neutral", key: "none" });
  assert.equal(summarizeRouting(output("radio_cable", { route: route(JBL), state: "missing" })).key, "missingDefault");
  assert.equal(summarizeRouting(output("radio_cable", { route: route(JBL, "mute"), state: "missing" })).key, "missingMuted");
  assert.deepEqual(summarizeRouting(output("radio_cable", { route: route(JBL), state: "routed" })), { tone: "info", key: "noPlayer" });
});

test("résumé : appliqué par le navigateur ou par le serveur, sinon le problème rapporté", () => {
  const base = { route: route(JBL), state: "routed" as const };
  assert.equal(summarizeRouting(output("radio_cable", { ...base, players: [player("unsupported"), player("applied", false, false)] })).key, "appliedBrowser");
  assert.equal(summarizeRouting(output("radio_cable", { ...base, players: [player("unsupported")], server: { status: "moved" } })).key, "appliedServer");
  const bad = summarizeRouting(output("radio_cable", { ...base, players: [player("needs_labels")] }));
  assert.deepEqual([bad.tone, bad.key], ["warn", "needsLabels"]);
  assert.equal(summarizeRouting(output("radio_cable", { ...base, players: [player("insecure")] })).key, "insecure");
  assert.equal(summarizeRouting(output("radio_cable", { ...base, players: [player("no_match")] })).key, "noMatch");
  assert.deepEqual(summarizeRouting(output("radio_cable", { ...base, players: [player("error")] })).tone, "bad");
});

test("résumé : le lecteur local prime sur un lecteur distant et le serveur explique pourquoi il n'a rien fait", () => {
  const base = { route: route(JBL), state: "routed" as const };
  const mixed = summarizeRouting(output("radio_cable", { ...base, players: [player("no_match", false, true), player("unsupported", true, false)] }));
  assert.equal(mixed.key, "unsupported");
  const ambiguous = summarizeRouting(output("radio_cable", { ...base, players: [player("unsupported")], server: { status: "ambiguous" } }));
  assert.deepEqual([ambiguous.key, ambiguous.extra], ["unsupported", "serverAmbiguous"]);
  assert.equal(summarizeRouting(output("radio_cable", { ...base, players: [player("unsupported")], server: { status: "failed" } })).extra, "serverFailed");
  assert.equal(summarizeRouting(output("radio_cable", { ...base, players: [player("unsupported")], server: { status: "no_stream" } })).extra, "serverNoStream");
  assert.deepEqual(summarizeRouting(output("radio_cable", { ...base, players: [player(null)] })), { tone: "info", key: "pending", extra: undefined });
});

test("libellés de sortie du navigateur masqués", () => {
  assert.equal(outputLabelsHidden([{ kind: "audiooutput", label: "" }, { kind: "audiooutput", label: "" }]), true);
  assert.equal(outputLabelsHidden([{ kind: "audiooutput", label: "" }, { kind: "audiooutput", label: "HDMI" }]), false);
  assert.equal(outputLabelsHidden([{ kind: "audioinput", label: "" }]), false);
  assert.equal(outputLabelsHidden([]), false);
});
