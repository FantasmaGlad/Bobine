import type { NetworkInfo } from "./types";

export function sameNetwork(a: NetworkInfo, b: NetworkInfo): boolean {
  return a.localIp === b.localIp && a.port === b.port && a.mdnsUrl === b.mdnsUrl;
}

export function logoNeedsReload(current: boolean, patch: { hasCustomLogo?: boolean; logoChanged?: boolean }): boolean {
  return patch.logoChanged === true || (patch.hasCustomLogo !== undefined && patch.hasCustomLogo !== current);
}
