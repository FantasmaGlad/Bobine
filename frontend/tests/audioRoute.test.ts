import { test } from "node:test";
import assert from "node:assert/strict";
import {
  applyRoute, matchOutputDevice, normalizeLabel, planRoute, sameRoute,
  type OutputDevice, type RadioRoute, type RouteDeps, type SinkContext,
} from "../src/lib/audioRoute.ts";

const route = (patch: Partial<RadioRoute> = {}): RadioRoute => ({
  key: "bt:88:92:CC:9C:41:0E", label: "JBL Live 770NC", match: ["JBL Live 770NC", "JBL Live"], kind: "bluetooth", fallback: "default", state: "routed", ...patch,
});
const dev = (deviceId: string, label: string): OutputDevice => ({ deviceId, label });
const ENV = { secure: true, canSetSinkId: true };

test("normalisation : casse, accents et ponctuation ignorés", () => {
  assert.equal(normalizeLabel("Écran  HDMI (Realtek)"), "ecran hdmi realtek");
  assert.equal(normalizeLabel(null), "");
  assert.equal(normalizeLabel(undefined), "");
});

test("correspondance exacte sur le nom du système, entrées virtuelles du navigateur jamais choisies", () => {
  const devices = [dev("default", "Default - JBL Live 770NC"), dev("communications", "Communications - JBL Live 770NC"), dev("abc", "Haut-parleurs"), dev("def", "JBL Live 770NC")];
  assert.deepEqual(matchOutputDevice(devices, ["JBL Live 770NC"]), { kind: "found", deviceId: "def" });
  assert.deepEqual(matchOutputDevice(devices, ["jbl live 770nc"]), { kind: "found", deviceId: "def" });
});

test("inclusion acceptée seulement si elle désigne UN SEUL périphérique", () => {
  const prefixed = [dev("a", "Bluetooth JBL Live 770NC"), dev("b", "Haut-parleurs")];
  assert.deepEqual(matchOutputDevice(prefixed, ["JBL Live 770NC"]), { kind: "found", deviceId: "a" });
  const twin = [dev("a", "USB Audio"), dev("b", "USB Audio 2")];
  assert.deepEqual(matchOutputDevice(twin, ["USB Audio"]), { kind: "found", deviceId: "a" }); // égalité exacte prioritaire
  const ambiguous = [dev("a", "USB Audio A"), dev("b", "USB Audio B")];
  assert.deepEqual(matchOutputDevice(ambiguous, ["USB Audio"]), { kind: "none" });
  const doubled = [dev("a", "HDMI"), dev("b", "hdmi")];
  assert.deepEqual(matchOutputDevice(doubled, ["HDMI"]), { kind: "none" }); // deux égalités exactes : on ne devine pas
});

test("libellés masqués par le navigateur : needs_labels ; liste vide : none", () => {
  assert.deepEqual(matchOutputDevice([dev("default", ""), dev("a", ""), dev("b", "")], ["x"]), { kind: "needs_labels" });
  assert.deepEqual(matchOutputDevice([], ["x"]), { kind: "none" });
  assert.deepEqual(matchOutputDevice([dev("default", "Default")], ["x"]), { kind: "none" });
  assert.deepEqual(matchOutputDevice([dev("a", "Haut-parleurs")], []), { kind: "none" });
});

test("plan : sans route, retour à la sortie par défaut", () => {
  assert.deepEqual(planRoute(null, ENV, null), { action: "default", status: "default" });
});

test("plan : sortie débranchée, repli par défaut ou sourdine selon le choix", () => {
  assert.deepEqual(planRoute(route({ state: "missing" }), ENV, []), { action: "default", status: "missing" });
  assert.deepEqual(planRoute(route({ state: "missing", fallback: "mute" }), ENV, []), { action: "mute", status: "muted" });
  // Même quand le navigateur ne sait pas router : la sourdine du repli ne dépend pas de setSinkId.
  assert.deepEqual(planRoute(route({ state: "missing", fallback: "mute" }), { secure: false, canSetSinkId: false }, null), { action: "mute", status: "muted" });
});

test("plan : limites du navigateur rendues visibles, jamais de coupure", () => {
  assert.deepEqual(planRoute(route(), { secure: true, canSetSinkId: false }, []), { action: "none", status: "unsupported" });
  assert.deepEqual(planRoute(route(), { secure: false, canSetSinkId: true }, []), { action: "none", status: "insecure" });
  assert.deepEqual(planRoute(route({ fallback: "mute" }), { secure: false, canSetSinkId: true }, []), { action: "none", status: "insecure" }); // « couper » ne vaut que sortie débranchée
  assert.deepEqual(planRoute(route(), ENV, null), { action: "none", status: "error" });
  assert.deepEqual(planRoute(route(), ENV, [dev("x", ""), dev("y", "")]), { action: "none", status: "needs_labels" });
  assert.deepEqual(planRoute(route(), ENV, [dev("x", "Haut-parleurs")]), { action: "none", status: "no_match" });
});

test("plan : état « inconnu » (liste des sorties du serveur indisponible) tente tout de même la correspondance", () => {
  assert.deepEqual(planRoute(route({ state: "unknown" }), ENV, [dev("d", "JBL Live 770NC")]), { action: "sink", deviceId: "d", status: "applied" });
});

test("sameRoute compare le contenu", () => {
  assert.ok(sameRoute(route(), route()));
  assert.ok(!sameRoute(route(), route({ fallback: "mute" })));
  assert.ok(sameRoute(null, null) && !sameRoute(null, route()));
});

function harness(options: { devices?: OutputDevice[] | Error; env?: RouteDeps["env"]; sinkId?: string; failSet?: boolean } = {}) {
  const calls: string[] = [];
  const mutes: boolean[] = [];
  const ctx: SinkContext = {
    sinkId: options.sinkId ?? "",
    setSinkId: async (id: string) => {
      calls.push(id);
      if (options.failSet) throw new Error("NotAllowedError");
      ctx.sinkId = id;
    },
  };
  const deps: RouteDeps = {
    env: options.env ?? ENV,
    listOutputs: async () => {
      if (options.devices instanceof Error) throw options.devices;
      return options.devices ?? [];
    },
    setMuted: (m) => mutes.push(m),
  };
  return { ctx, deps, calls, mutes };
}

test("application : trouve le périphérique, appelle setSinkId une seule fois, pas de re-application inutile", async () => {
  const h = harness({ devices: [dev("def", "JBL Live 770NC")] });
  assert.equal(await applyRoute(h.ctx, route(), h.deps), "applied");
  assert.deepEqual(h.calls, ["def"]);
  assert.equal(await applyRoute(h.ctx, route(), h.deps), "applied");
  assert.deepEqual(h.calls, ["def"]); // déjà sur cette sortie
  assert.deepEqual(h.mutes, [false, false]);
});

test("application : effacement de la route, retour à la sortie par défaut seulement si on l'avait quittée", async () => {
  const h = harness({ devices: [dev("def", "JBL Live 770NC")] });
  assert.equal(await applyRoute(h.ctx, null, h.deps), "default");
  assert.deepEqual(h.calls, []); // jamais routé : rien à défaire
  await applyRoute(h.ctx, route(), h.deps);
  assert.equal(await applyRoute(h.ctx, null, h.deps), "default");
  assert.deepEqual(h.calls, ["def", ""]);
});

test("application : sortie absente, repli couper = sourdine et retour à la sortie par défaut", async () => {
  const h = harness({ sinkId: "def" });
  assert.equal(await applyRoute(h.ctx, route({ state: "missing", fallback: "mute" }), h.deps), "muted");
  assert.deepEqual(h.mutes, [true]);
  assert.deepEqual(h.calls, [""]);
  assert.equal(await applyRoute(h.ctx, route({ state: "routed" }), harness({ devices: [dev("def", "JBL Live")] }).deps), "applied"); // levée de la sourdine côté appelant
});

test("application : le navigateur refuse ou ne répond pas, statut error sans exception", async () => {
  const refused = harness({ devices: [dev("def", "JBL Live 770NC")], failSet: true });
  assert.equal(await applyRoute(refused.ctx, route(), refused.deps), "error");
  const broken = harness({ devices: new Error("enumerateDevices a échoué") });
  assert.equal(await applyRoute(broken.ctx, route(), broken.deps), "error");
  assert.equal(await applyRoute(null, route(), harness().deps), "error");
  assert.equal(await applyRoute(null, null, harness().deps), "default");
});

test("application : navigateur sans setSinkId ou contexte non sécurisé, aucun appel et aucune sourdine", async () => {
  const unsupported = harness({ env: { secure: true, canSetSinkId: false } });
  assert.equal(await applyRoute(unsupported.ctx, route(), unsupported.deps), "unsupported");
  const insecure = harness({ env: { secure: false, canSetSinkId: true } });
  assert.equal(await applyRoute(insecure.ctx, route(), insecure.deps), "insecure");
  assert.deepEqual([...unsupported.calls, ...insecure.calls], []);
  assert.deepEqual([...unsupported.mutes, ...insecure.mutes], [false, false]);
});
