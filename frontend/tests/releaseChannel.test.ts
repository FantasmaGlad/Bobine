import { test } from "node:test";
import assert from "node:assert/strict";
import {
  applyChannelFavicon,
  channelFaviconUrl,
  channelLogoUrl,
  DEFAULT_RELEASE_CHANNEL,
  isReleaseChannel,
  RELEASE_CHANNELS,
} from "../src/lib/releaseChannel.ts";

type FakeLink = { rel: string; href: string; type: string; sizes?: string; removeAttribute(name: string): void };

function fakeLink(rel: string): FakeLink {
  const link: FakeLink = {
    rel, href: "/favicon.ico", type: "image/x-icon", sizes: "48x48",
    removeAttribute(name: string) { if (name === "sizes") delete link.sizes; },
  };
  return link;
}

function fakeDocument(existing: FakeLink[]) {
  const head: FakeLink[] = [];
  const doc = {
    querySelectorAll: () => existing,
    createElement: () => fakeLink(""),
    head: { appendChild: (node: FakeLink) => head.push(node) },
  } as unknown as Document;
  return { doc, head };
}

test("les trois canaux, Stable par défaut", () => {
  assert.deepEqual([...RELEASE_CHANNELS], ["stable", "beta", "canary"]);
  assert.equal(DEFAULT_RELEASE_CHANNEL, "stable");
  assert.ok(isReleaseChannel("canary"));
  assert.ok(!isReleaseChannel("nightly") && !isReleaseChannel(null));
});

test("une URL de logo et de favicon par canal", () => {
  for (const channel of RELEASE_CHANNELS) {
    assert.equal(channelLogoUrl(channel), `/logo-${channel}.png`);
    assert.equal(channelFaviconUrl(channel), `/favicon-${channel}.png`);
  }
});

test("le favicon du canal remplace tous les liens d'icône existants", () => {
  const a = fakeLink("icon");
  const b = fakeLink("shortcut icon");
  const { doc, head } = fakeDocument([a, b]);
  applyChannelFavicon(doc, "beta");
  for (const link of [a, b]) {
    assert.equal(link.href, "/favicon-beta.png");
    assert.equal(link.type, "image/png");
    assert.equal(link.sizes, undefined);
  }
  assert.equal(head.length, 0);
});

test("sans lien d'icône dans la page, un lien est créé", () => {
  const { doc, head } = fakeDocument([]);
  applyChannelFavicon(doc, "canary");
  assert.equal(head.length, 1);
  assert.equal(head[0].rel, "icon");
  assert.equal(head[0].href, "/favicon-canary.png");
});
