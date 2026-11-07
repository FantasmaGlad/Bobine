/** Adresse d'une route de l'API : même origine, sauf en développement (page sur le port 3000, API sur 8001). */
export function getApiUrl(path: string): string {
  if (typeof window !== "undefined" && window.location.port === "3000") return `http://localhost:8001/api${path}`;
  return `/api${path}`;
}
