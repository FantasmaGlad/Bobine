export const SAFE_MARGIN_STORAGE_KEY = "bobine.screenSafeMargin";
export const SAFE_MARGIN_MAX = 10;

export function parseSafeMargin(raw: string | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const trimmed = raw.trim().replace(",", ".");
  if (trimmed === "") return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return null;
  return Math.min(SAFE_MARGIN_MAX, Math.max(0, Math.round(value * 10) / 10));
}

export function safeMarginCss(percent: number): { x: string; y: string } {
  const p = Math.min(SAFE_MARGIN_MAX, Math.max(0, percent));
  return { x: `${p}vw`, y: `${p}vh` };
}
