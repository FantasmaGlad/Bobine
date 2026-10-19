import { test } from "node:test";
import assert from "node:assert/strict";
import { isFullscreenPath } from "../src/lib/fullscreenRoutes.ts";

test("les écrans de diffusion sont plein écran, avec ou sans slash final", () => {
  for (const path of ["/kiosk", "/kiosk/", "/cinema", "/cinema/", "/coach", "/coach/", "/grid", "/grid/", "/radio", "/radio/"]) {
    assert.equal(isFullscreenPath(path), true, path);
  }
});

test("les pages d'administration radio restent des pages normales (pas de préfixe)", () => {
  for (const path of ["/radio-library", "/radio-remote", "/radio-announcements", "/radio-library/", "/radiology"]) {
    assert.equal(isFullscreenPath(path), false, path);
  }
});

test("les autres pages d'administration ne sont pas plein écran", () => {
  for (const path of ["/", "/dashboard-cable", "/dashboard-network", "/library", "/schedule", "/settings", "/audio"]) {
    assert.equal(isFullscreenPath(path), false, path);
  }
});

test("pathname absent ou vide", () => {
  assert.equal(isFullscreenPath(null), false);
  assert.equal(isFullscreenPath(undefined), false);
  assert.equal(isFullscreenPath(""), false);
});
