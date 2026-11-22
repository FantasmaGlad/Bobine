import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_REMOTE_BINDINGS, gamepadBindings, keyBinding, pickHandler } from "../src/lib/remoteBindings.ts";

const handler = (name: string) => Object.assign(() => {}, { label: name });
const pick = (key: string, keyCode: number, handlers: Record<string, () => void>) =>
  pickHandler(handlers, keyBinding(DEFAULT_REMOTE_BINDINGS, key, keyCode));

test("le nom de touche prime sur le code Android", () => {
  assert.deepEqual(keyBinding(DEFAULT_REMOTE_BINDINGS, "ArrowLeft", 22), ["left"]);
  assert.deepEqual(keyBinding(DEFAULT_REMOTE_BINDINGS, "Unidentified", 166), ["chapter_next", "next"]);
  assert.equal(keyBinding(DEFAULT_REMOTE_BINDINGS, "Unidentified", 999), undefined);
});

test("une touche connue sans action dans la page ne retombe pas sur son code", () => {
  assert.equal(pick("ArrowLeft", 23, { enter: handler("enter") }), undefined);
});

test("les chaînes de repli suivent l'ordre de préférence", () => {
  const next = handler("next");
  const chapter = handler("chapter");
  assert.equal(pick("ChannelUp", 0, { next }), next);
  assert.equal(pick("ChannelUp", 0, { next, chapter_next: chapter }), chapter);
  const enter = handler("enter");
  assert.equal(pick(" ", 0, { enter }), enter);
  const up = handler("up");
  assert.equal(pick("PageUp", 0, { up }), up);
});

test("la manette garde l'ordre et les boutons d'origine", () => {
  assert.deepEqual(gamepadBindings(DEFAULT_REMOTE_BINDINGS).map(([button]) => button), [12, 13, 14, 15, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.deepEqual(Object.fromEntries(gamepadBindings(DEFAULT_REMOTE_BINDINGS))[0], ["enter", "play_pause"]);
});

test("chaque touche de l'ancienne table garde son action", () => {
  const expected: Record<string, string> = {
    Escape: "back", Backspace: "back", MediaStop: "back", Select: "enter", MediaPause: "play_pause",
    FastForward: "next", MediaRewind: "prev", VolumeMute: "mute", AudioVolumeUp: "volume_up",
  };
  for (const [key, action] of Object.entries(expected)) assert.deepEqual(keyBinding(DEFAULT_REMOTE_BINDINGS, key, 0), [action], key);
  const codes: Record<number, string> = { 4: "back", 19: "up", 23: "enter", 66: "enter", 85: "play_pause", 127: "play_pause", 87: "next", 164: "mute" };
  for (const [code, action] of Object.entries(codes)) assert.deepEqual(keyBinding(DEFAULT_REMOTE_BINDINGS, "Unidentified", Number(code)), [action], code);
});
