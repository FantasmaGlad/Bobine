import test from "node:test";
import assert from "node:assert/strict";
import { subtitleSrc } from "../src/lib/subtitles.ts";

const getApiUrl = (path: string) => `/api${path}`;

test("subtitleSrc ne double pas le préfixe /api renvoyé par le serveur", () => {
  assert.equal(subtitleSrc(getApiUrl, "/api/videos/1/subtitles/2/vtt"), "/api/videos/1/subtitles/2/vtt");
});

test("subtitleSrc accepte une URL sans préfixe", () => {
  assert.equal(subtitleSrc(getApiUrl, "/videos/1/subtitles/2/vtt"), "/api/videos/1/subtitles/2/vtt");
});

test("subtitleSrc ne touche pas un segment qui commence par api", () => {
  assert.equal(subtitleSrc(getApiUrl, "/apiary/x"), "/api/apiary/x");
});
