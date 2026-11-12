/** Hôte de l'API : celui de la page, sauf en développement (page sur le port 3000, API sur 8001). */
function isDevServer(): boolean {
  return typeof window !== "undefined" && window.location.port === "3000";
}

/** Adresse d'une route de l'API. */
export function getApiUrl(path: string): string {
  return isDevServer() ? `http://localhost:8001/api${path}` : `/api${path}`;
}

/** Adresse du WebSocket commun (lecture, radio, appareils, stockage) ; vide hors navigateur. */
export function getPlaybackWsUrl(): string {
  if (typeof window === "undefined") return "";
  const host = isDevServer() ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}
