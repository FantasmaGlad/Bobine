import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ChunkedUnsupportedError, MAX_ATTEMPTS, SESSION_TIMEOUT_MS, UploadAbortedError, UploadNoticeError, uploadFileInChunks,
  type ChunkedUploadOptions,
} from "../src/lib/chunkedUpload.ts";
import type { UploadNotice, UploadPhase } from "../src/lib/uploadFlow.ts";

const CHUNK = 10;
const file = (size: number) => new File([new Uint8Array(size)], "cours.mov");
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const session = (size: number, offset = 0) => ({ upload_id: "a".repeat(32), offset, size, complete: false, chunk_size: CHUNK });

interface Harness {
  opts: ChunkedUploadOptions;
  phases: UploadPhase[];
  notices: Array<UploadNotice | null>;
  sleeps: number[];
}

type Deps = NonNullable<ChunkedUploadOptions["deps"]>;

function harness(deps: Deps, signal: AbortSignal = new AbortController().signal): Harness {
  const phases: UploadPhase[] = [];
  const notices: Array<UploadNotice | null> = [];
  const sleeps: number[] = [];
  const opts: ChunkedUploadOptions = {
    apiUrl: (p) => `/api${p}`,
    onProgress: () => {},
    onPhase: (p) => phases.push(p),
    onNotice: (n) => notices.push(n),
    signal,
    deps: { sleepImpl: async (ms) => { sleeps.push(ms); }, ...deps },
  };
  return { opts, phases, notices, sleeps };
}

/** fetch factice : réponses par route ; un handler qui renvoie `"hang"` ne répond jamais (comme un serveur gelé). */
function fakeFetch(routes: { post: () => Response | "hang" | Error; get?: () => Response | Error }): typeof fetch {
  return ((input: string, init?: RequestInit) => new Promise((resolve, reject) => {
    const handler = init?.method === "POST" ? routes.post : routes.get;
    const out = handler ? handler() : new Error("route inattendue");
    if (out === "hang") {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
      return;
    }
    if (out instanceof Error) return reject(out);
    resolve(out);
  })) as typeof fetch;
}

test("création de session sans réponse : erreur explicite au bout du délai, plus de 0 % muet", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = harness({ fetchImpl: fakeFetch({ post: () => "hang" }) });
  const pending = uploadFileInChunks(file(25), h.opts);
  const assertion = assert.rejects(pending, (err: unknown) => {
    assert.ok(err instanceof UploadNoticeError);
    assert.equal(err.key, "uploads.errors.sessionTimeout");
    assert.equal(err.fatal, true);
    assert.match(err.message, /ne répond pas/);
    return true;
  });
  t.mock.timers.tick(SESSION_TIMEOUT_MS);
  await assertion;
  assert.deepEqual(h.phases, ["connecting"]);
});

test("serveur injoignable à la création : erreur explicite et non réessayée", async () => {
  const h = harness({ fetchImpl: fakeFetch({ post: () => new TypeError("Failed to fetch") }) });
  await assert.rejects(uploadFileInChunks(file(25), h.opts), (err: unknown) => err instanceof UploadNoticeError && err.key === "uploads.errors.unreachable" && err.fatal);
});

test("annulation pendant la création de session : UploadAbortedError, pas une erreur de délai", async () => {
  const ctrl = new AbortController();
  const h = harness({ fetchImpl: fakeFetch({ post: () => "hang" }) }, ctrl.signal);
  const pending = uploadFileInChunks(file(25), h.opts);
  ctrl.abort();
  await assert.rejects(pending, UploadAbortedError);
});

test("ancien serveur (404/405) : ChunkedUnsupportedError inchangé", async () => {
  for (const status of [404, 405]) {
    const h = harness({ fetchImpl: fakeFetch({ post: () => json(status, {}) }) });
    await assert.rejects(uploadFileInChunks(file(25), h.opts), ChunkedUnsupportedError);
  }
});

test("refus du serveur à la création (disque plein) : le détail du serveur est repris tel quel", async () => {
  const h = harness({ fetchImpl: fakeFetch({ post: () => json(507, { detail: "Espace disque insuffisant" }) }) });
  await assert.rejects(uploadFileInChunks(file(25), h.opts), /Espace disque insuffisant/);
});

test("envoi nominal : phases connecting puis sending, aucun message d'état", async () => {
  const sent: number[] = [];
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(25)) }),
    sendChunkImpl: async (_id, _f, offset, end) => { sent.push(offset); return { status: 200, offset: end }; },
  });
  const id = await uploadFileInChunks(file(25), h.opts);
  assert.equal(id, "a".repeat(32));
  assert.deepEqual(sent, [0, 10, 20]);
  assert.deepEqual(h.phases, ["connecting", "sending"]);
  assert.ok(h.notices.every((n) => n === null));
  assert.deepEqual(h.sleeps, []);
});

test("morceau qui échoue puis réussit : reprise visible (n/8) puis message effacé", async () => {
  let calls = 0;
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(10)), get: () => json(200, { offset: 0 }) }),
    sendChunkImpl: async (_id, _f, offset, end) => {
      calls += 1;
      if (calls <= 2) throw new UploadNoticeError("uploads.reason.stalled", "Aucune donnée transmise");
      return { status: 200, offset: end };
    },
  });
  await uploadFileInChunks(file(10), h.opts);
  assert.deepEqual(h.notices.filter(Boolean), [
    { key: "uploads.retrying", params: { attempt: 2, max: MAX_ATTEMPTS } },
    { key: "uploads.retrying", params: { attempt: 3, max: MAX_ATTEMPTS } },
  ]);
  assert.equal(h.notices.at(-1), null);
  assert.deepEqual(h.sleeps, [1000, 2000]);
});

test("erreur 5xx : message de reprise propre au statut", async () => {
  let calls = 0;
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(10)), get: () => json(200, { offset: 0 }) }),
    sendChunkImpl: async (_id, _f, _o, end) => (++calls === 1 ? { status: 503, offset: 0 } : { status: 200, offset: end }),
  });
  await uploadFileInChunks(file(10), h.opts);
  assert.deepEqual(h.notices[0], { key: "uploads.retryingServerError", params: { attempt: 2, max: MAX_ATTEMPTS, status: 503 } });
});

test("morceau refusé en boucle sans progrès : abandon après MAX_ATTEMPTS avec la raison", async () => {
  let calls = 0;
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(10)), get: () => json(200, { offset: 0 }) }),
    sendChunkImpl: async () => { calls += 1; return { status: 502, offset: 0 }; },
  });
  await assert.rejects(uploadFileInChunks(file(10), h.opts), (err: unknown) => {
    assert.ok(err instanceof UploadNoticeError);
    assert.equal(err.key, "uploads.errors.interrupted");
    assert.equal(err.fatal, true);
    assert.deepEqual(err.params, { max: MAX_ATTEMPTS, reasonKey: "uploads.reason.server", status: 502 });
    return true;
  });
  assert.equal(calls, MAX_ATTEMPTS);
  assert.equal(h.sleeps.length, MAX_ATTEMPTS - 1);
  assert.equal(Math.max(...h.sleeps), 15000);
});

test("refus définitif (4xx) : aucune reprise, détail du serveur conservé", async () => {
  let calls = 0;
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(10)) }),
    sendChunkImpl: async () => { calls += 1; return { status: 413, offset: 0, detail: "Le morceau dépasse la taille annoncée du fichier" }; },
  });
  await assert.rejects(uploadFileInChunks(file(10), h.opts), /dépasse la taille annoncée/);
  assert.equal(calls, 1);
  assert.deepEqual(h.sleeps, []);
});

test("des octets conservés par le serveur comptent comme un progrès : le compteur de tentatives repart", async () => {
  // Chaque morceau échoue une fois en laissant 1 octet de plus côté serveur : 12 échecs au total (> MAX_ATTEMPTS)
  // mais jamais 8 d'affilée sans progrès.
  const size = 12;
  let serverOffset = 0;
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, { ...session(size), chunk_size: size }), get: () => json(200, { offset: serverOffset }) }),
    sendChunkImpl: async (_id, _f, _o, end) => {
      if (serverOffset < size - 1) { serverOffset += 1; throw new UploadNoticeError("uploads.reason.timeout", "Délai dépassé"); }
      serverOffset = end;
      return { status: 200, offset: end };
    },
  });
  await uploadFileInChunks(file(size), h.opts);
  assert.equal(serverOffset, size);
});

test("désynchronisation (409) : reprise à l'offset réel sans compter d'échec", async () => {
  const offsets: number[] = [];
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(20)) }),
    sendChunkImpl: async (_id, _f, offset, end) => {
      offsets.push(offset);
      return offsets.length === 1 ? { status: 409, offset: 10 } : { status: 200, offset: end };
    },
  });
  await uploadFileInChunks(file(20), h.opts);
  assert.deepEqual(offsets, [0, 10]);
  assert.deepEqual(h.sleeps, []);
});

test("session introuvable à la resynchronisation (serveur redémarré) : erreur explicite immédiate", async () => {
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(10)), get: () => json(404, { detail: "introuvable" }) }),
    sendChunkImpl: async () => { throw new UploadNoticeError("uploads.reason.network", "Erreur réseau"); },
  });
  await assert.rejects(uploadFileInChunks(file(10), h.opts), (err: unknown) => err instanceof UploadNoticeError && err.key === "uploads.errors.sessionLost");
});

test("annulation pendant l'attente d'une reprise : UploadAbortedError", async () => {
  const ctrl = new AbortController();
  const h = harness({
    fetchImpl: fakeFetch({ post: () => json(201, session(10)), get: () => json(200, { offset: 0 }) }),
    sendChunkImpl: async () => { throw new UploadNoticeError("uploads.reason.network", "Erreur réseau"); },
    sleepImpl: async (_ms, signal) => { ctrl.abort(); if (signal.aborted) throw new UploadAbortedError(); },
  }, ctrl.signal);
  await assert.rejects(uploadFileInChunks(file(10), h.opts), UploadAbortedError);
});
