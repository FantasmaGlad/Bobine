export interface BobineNativeBridge {
  setThemeColors(background: string, text: string): void;
  setThemeAccent?(accent: string): void;
  setUpdateChannel?(channel: string): void;
  getStartOnBoot(): boolean;
  setStartOnBoot(enabled: boolean): void;
}

export function getNativeBridge(): BobineNativeBridge | null {
  if (typeof window === "undefined") return null;
  const bridge = (window as unknown as { BobineNative?: BobineNativeBridge }).BobineNative;
  return bridge ?? null;
}

function toHex(cssColor: string): string | null {
  const match = /rgba?\((\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(cssColor);
  if (!match) return null;
  return `#${[match[1], match[2], match[3]].map((v) => Number(v).toString(16).padStart(2, "0")).join("")}`;
}

export function pushThemeToNative(): void {
  const bridge = getNativeBridge();
  if (!bridge || typeof document === "undefined") return;
  const style = getComputedStyle(document.body);
  const background = toHex(style.backgroundColor);
  const text = toHex(style.color);
  if (background && text) bridge.setThemeColors(background, text);
  const accent = readAccentHex();
  if (accent && typeof bridge.setThemeAccent === "function") {
    try {
      bridge.setThemeAccent(accent);
    } catch {
    }
  }
}

function readAccentHex(): string | null {
  const probe = document.createElement("span");
  probe.style.color = "var(--accent-text)";
  probe.style.display = "none";
  document.body.appendChild(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  return toHex(color);
}

export function pushUpdateChannelToNative(channel: string): void {
  const bridge = getNativeBridge();
  if (!bridge || typeof bridge.setUpdateChannel !== "function") return;
  try {
    bridge.setUpdateChannel(channel);
  } catch {
  }
}
