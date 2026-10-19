import { test } from "node:test";
import assert from "node:assert/strict";
import { parseSafeMargin, safeMarginCss, SAFE_MARGIN_MAX } from "../src/lib/screenSafe.ts";

test("parseSafeMargin accepte les nombres et borne à [0, max]", () => {
  assert.equal(parseSafeMargin("3"), 3);
  assert.equal(parseSafeMargin("2,5"), 2.5);
  assert.equal(parseSafeMargin("0"), 0);
  assert.equal(parseSafeMargin("42"), SAFE_MARGIN_MAX);
  assert.equal(parseSafeMargin("-4"), 0);
});

test("parseSafeMargin rejette les valeurs invalides", () => {
  assert.equal(parseSafeMargin(null), null);
  assert.equal(parseSafeMargin(undefined), null);
  assert.equal(parseSafeMargin(""), null);
  assert.equal(parseSafeMargin("abc"), null);
  assert.equal(parseSafeMargin("Infinity"), null);
});

test("safeMarginCss exprime la marge en vw / vh", () => {
  assert.deepEqual(safeMarginCss(4), { x: "4vw", y: "4vh" });
  assert.deepEqual(safeMarginCss(99), { x: `${SAFE_MARGIN_MAX}vw`, y: `${SAFE_MARGIN_MAX}vh` });
});
