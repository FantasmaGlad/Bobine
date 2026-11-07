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

type Translate = (key: string, params?: Record<string, string | number>) => string;

/** Libellé de la qualité audio ; `t` donne les mots de la langue de l'interface (français par défaut). */
export function getAudioQualityBadge(
  channels?: number | null,
  codec?: string | null,
  fallback?: string | null,
  t?: Translate
): string | null {
  const tr: Translate = t ?? ((key, params) => (
    key === "audioBadge.stereo" ? "Stéréo 2.0" : key === "audioBadge.stereoCodec" ? `Stéréo (${params?.codec})` : `${params?.count} canaux`
  ));
  const stereo = tr("audioBadge.stereo");
  if (channels === 6) return "Surround 5.1";
  if (channels === 8) return "Surround 7.1";
  if (channels === 2) return stereo;
  if (channels === 1) return "Mono 1.0";
  if (channels && channels > 2) return tr("audioBadge.channels", { count: channels });
  if (codec) {
    const c = codec.toUpperCase();
    if (c === "AC3" || c === "EAC3") return "Surround 5.1";
    return tr("audioBadge.stereoCodec", { codec: c });
  }
  return fallback === undefined ? stereo : fallback;
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
