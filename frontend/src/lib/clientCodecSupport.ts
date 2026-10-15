/**
 * Capacités de décodage vidéo du navigateur, annoncées au serveur pour qu'il
 * serve la version « lisible partout » quand l'original ne peut pas être décodé
 * (côté serveur : `app/utils/web_profile.py`).
 *
 * `canPlayType` est SYNCHRONE : la décision peut être prise au moment exact où
 * l'on assigne `video.src`, sans état asynchrone à attendre. Le résultat est
 * mis en cache (les capacités d'un navigateur ne changent pas pendant une
 * session). Détection de FONCTIONNALITÉS uniquement — jamais `navigator.userAgent`.
 */

export type VideoProfilePreference = "auto" | "web" | "original";

const PROFILE_STORAGE_KEY = "bobine.videoProfile";

/** Codec string représentatif par capacité (mêmes identifiants que le backend). */
const PROBES: ReadonlyArray<readonly [string, string]> = [
  ["h264", 'video/mp4; codecs="avc1.640028"'],
  ["hevc", 'video/mp4; codecs="hvc1.1.6.L93.B0"'],
  ["vp9", 'video/mp4; codecs="vp09.00.10.08"'],
  ["av1", 'video/mp4; codecs="av01.0.08M.08"'],
  // H.264 High 10 : sert de sonde pour les vidéos 10 bits / 4:2:2 / 4:4:4
  ["hi10", 'video/mp4; codecs="avc1.6E0028"'],
];

let cachedAccept: string | null = null;

/** Capacités annoncées, ex. `h264,hevc,vp9,av1`. Chaîne vide côté serveur (SSR). */
export function getAcceptedCodecs(): string {
  if (cachedAccept !== null) return cachedAccept;
  if (typeof document === "undefined") return "";
  try {
    const probe = document.createElement("video");
    cachedAccept = PROBES.filter(([, type]) => probe.canPlayType(type) !== "").map(([name]) => name).join(",");
  } catch {
    cachedAccept = "";
  }
  return cachedAccept;
}

export function getVideoProfilePreference(): VideoProfilePreference {
  try {
    const value = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    return value === "web" || value === "original" ? value : "auto";
  } catch {
    return "auto"; // stockage indisponible (navigation privée stricte…) : comportement par défaut
  }
}

export function setVideoProfilePreference(value: VideoProfilePreference): void {
  try {
    if (value === "auto") window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    else window.localStorage.setItem(PROFILE_STORAGE_KEY, value);
  } catch {
    // préférence non persistée : sans conséquence
  }
}

/** Paramètres de requête à ajouter à l'URL du flux d'une vidéo. */
export function videoStreamQuery(): string {
  if (typeof window === "undefined") return "";
  const preference = getVideoProfilePreference();
  const params = new URLSearchParams();
  const accept = getAcceptedCodecs();
  if (accept) params.set("accept", accept);
  if (preference !== "auto") params.set("profile", preference);
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** URL du flux d'une vidéo avec négociation de la version servie. */
export function videoStreamUrl(apiUrl: (path: string) => string, videoId: number | string): string {
  return `${apiUrl(`/videos/${videoId}/stream`)}${videoStreamQuery()}`;
}
