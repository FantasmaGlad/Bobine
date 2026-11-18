import { test } from "node:test";
import assert from "node:assert/strict";
import { thumbnailUrl } from "../src/lib/thumbnail.ts";
import { courseThumbSrc } from "../src/lib/courseMeta.ts";

test("thumbnails are served by file name", () => {
  assert.equal(thumbnailUrl("/var/lib/bobine/thumbnails/a.jpg"), "/api/thumbnails/a.jpg");
  assert.equal(thumbnailUrl("b.webp"), "/api/thumbnails/b.webp");
});

test("missing thumbnails give no url", () => {
  for (const path of [null, undefined, "", "dir/"]) assert.equal(thumbnailUrl(path), null);
});

test("a course prefers its thumbnail url", () => {
  assert.equal(courseThumbSrc({ thumbnail_url: "u.jpg", thumbnail_path: "/x/p.jpg" }), "/api/thumbnails/u.jpg");
  assert.equal(courseThumbSrc({ thumbnail_url: null, thumbnail_path: "/x/p.jpg" }), "/api/thumbnails/p.jpg");
});
