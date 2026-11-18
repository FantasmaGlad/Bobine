import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { requestJson } from "../src/lib/apiRequest.ts";
import { devicesRequest } from "../src/lib/devices/request.ts";
import { storageRequest } from "../src/lib/storage/request.ts";

const realFetch = globalThis.fetch;
const calls: { url: string; init: RequestInit }[] = [];

function answer(status: number, body: string) {
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(body, { status });
  }) as typeof fetch;
}

afterEach(() => {
  globalThis.fetch = realFetch;
  calls.length = 0;
});

test("a body is sent as json with post", async () => {
  answer(200, '{"a":1}');
  assert.deepEqual(await requestJson("/api/x", { body: { b: 2 } }), { ok: true, data: { a: 1 } });
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.body, '{"b":2}');
});

test("an error status is parsed and an empty body is null", async () => {
  answer(200, "");
  assert.deepEqual(await requestJson("/api/x"), { ok: true, data: null });
  answer(409, '{"detail":{"code":"busy","message":"occupé"}}');
  const result = await requestJson("/api/x");
  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.error.status, 409);
});

test("a network failure becomes a network error", async () => {
  globalThis.fetch = (async () => { throw new TypeError("offline"); }) as typeof fetch;
  const result = await requestJson("/api/x");
  assert.equal(!result.ok && result.error.code, "network");
});

test("storage sends credentials, devices does not", async () => {
  answer(200, "{}");
  await storageRequest("/status");
  await devicesRequest("/status");
  assert.deepEqual(calls.map((c) => [c.url, c.init.credentials]), [["/api/storage/status", "include"], ["/api/devices/status", undefined]]);
});
