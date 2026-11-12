function isDevServer(): boolean {
  return typeof window !== "undefined" && window.location.port === "3000";
}

export function getApiUrl(path: string): string {
  return isDevServer() ? `http://localhost:8001/api${path}` : `/api${path}`;
}

export function getPlaybackWsUrl(): string {
  if (typeof window === "undefined") return "";
  const host = isDevServer() ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}
