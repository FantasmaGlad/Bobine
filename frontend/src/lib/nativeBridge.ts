/** Pont vers l'application Android (`window.BobineNative`), absent partout ailleurs. */
export interface BobineNativeBridge {
  setThemeColors(background: string, text: string): void;
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

/** Transmet fond et texte du thème actif à l'application, pour son écran de chargement. */
export function pushThemeToNative(): void {
  const bridge = getNativeBridge();
  if (!bridge || typeof document === "undefined") return;
  const style = getComputedStyle(document.body);
  const background = toHex(style.backgroundColor);
  const text = toHex(style.color);
  if (background && text) bridge.setThemeColors(background, text);
}
