import { test } from "node:test";
import assert from "node:assert/strict";
import { isServedImage, safeLinkUrl } from "../src/lib/safeUrl.ts";

test("links keep only http and https", () => {
  assert.equal(safeLinkUrl("https://github.com/x"), "https://github.com/x");
  assert.equal(safeLinkUrl(" HTTP://bobine.local/ "), "HTTP://bobine.local/");
  for (const url of ["javascript:alert(1)", " JavaScript:alert(1)", "data:text/html,x", "vbscript:x", "//evil.example", "relative"]) {
    assert.equal(safeLinkUrl(url), null, url);
  }
});

test("images are shown only from the server or inline data", () => {
  assert.equal(isServedImage("/api/branding/logo.png"), true);
  assert.equal(isServedImage("data:image/png;base64,AAAA"), true);
  for (const src of ["https://raw.githubusercontent.com/x/main/Assets/a.svg", "//cdn.example/a.png", "javascript:x", "data:text/html,x"]) {
    assert.equal(isServedImage(src), false, src);
  }
});
