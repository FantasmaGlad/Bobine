/**
 * Helpers pour le formatage des badges de qualité audio et vidéo.
 * Utilisés sur l'écran de pause (épuré : qualité audio + vidéo uniquement)
 * et dans la bibliothèque (détails techniques complets).
 */

export function getResolutionBadge(
  width?: number | null,
  height?: number | null,
  fallback: string | null = null
): string | null {
  if (!width && !height) return fallback;
  const w = width ?? 0;
  const h = height ?? 0;
  if (w >= 3840 || h >= 2160) return "4K Ultra HD";
  if (w >= 2560 || h >= 1440) return "1440p QHD";
  if (w >= 1920 || h >= 1080) return "1080p Full HD";
  if (w >= 1280 || h >= 720) return "720p HD";
  if (w > 0 || h > 0) return "SD";
  return fallback;
}

export function getAudioQualityBadge(
  channels?: number | null,
  codec?: string | null,
  fallback: string | null = "Stéréo 2.0"
): string | null {
  if (channels === 6) return "Surround 5.1";
  if (channels === 8) return "Surround 7.1";
  if (channels === 2) return "Stéréo 2.0";
  if (channels === 1) return "Mono 1.0";
  if (channels && channels > 2) return `${channels} canaux`;
  if (codec) {
    const c = codec.toUpperCase();
    if (c === "AC3" || c === "EAC3") return "Surround 5.1";
    return `Stéréo (${c})`;
  }
  return fallback;
}

export function formatFps(fps?: number | null): string | null {
  if (!fps || fps <= 0) return null;
  const rounded = Math.round(fps * 10) / 10;
  return `${rounded} fps`;
}

export function formatBitrate(kbps?: number | null): string | null {
  if (!kbps || kbps <= 0) return null;
  if (kbps >= 1000) {
    return `${(kbps / 1000).toFixed(1)} Mbps`;
  }
  return `${kbps} kbps`;
}
