import { DEFAULT_RELEASE_CHANNEL, RELEASE_CHANNELS, ROLLING_RELEASE_CHANNELS } from "./releaseChannels.generated.ts";

export { DEFAULT_RELEASE_CHANNEL, RELEASE_CHANNELS, ROLLING_RELEASE_CHANNELS };
export type UpdateChannel = (typeof RELEASE_CHANNELS)[number];

export function isReleaseChannel(value: unknown): value is UpdateChannel {
  return typeof value === "string" && (RELEASE_CHANNELS as readonly string[]).includes(value);
}

export function isRollingReleaseChannel(channel: UpdateChannel): boolean {
  return (ROLLING_RELEASE_CHANNELS as readonly string[]).includes(channel);
}

export function channelI18nSuffix(channel: UpdateChannel): string {
  return channel.charAt(0).toUpperCase() + channel.slice(1);
}

export function channelLogoUrl(channel: UpdateChannel): string {
  return `/logo-${channel}.png`;
}

export function channelFaviconUrl(channel: UpdateChannel): string {
  return `/favicon-${channel}.png`;
}

export function applyChannelFavicon(
  doc: Pick<Document, "querySelectorAll" | "createElement" | "head">,
  channel: UpdateChannel,
): void {
  const url = channelFaviconUrl(channel);
  const links = Array.from(doc.querySelectorAll<HTMLLinkElement>('link[rel="icon"], link[rel="shortcut icon"]'));
  if (links.length === 0) {
    const created = doc.createElement("link");
    created.rel = "icon";
    doc.head.appendChild(created);
    links.push(created);
  }
  for (const link of links) {
    link.type = "image/png";
    link.removeAttribute("sizes");
    link.href = url;
  }
}
