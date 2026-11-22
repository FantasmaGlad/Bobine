import { getApiUrl } from "@/lib/apiUrl";
import { DEFAULT_REMOTE_BINDINGS, parseRemoteBindings, type RemoteBindings } from "@/lib/remoteBindings";

let current: RemoteBindings = DEFAULT_REMOTE_BINDINGS;
let loading: Promise<void> | null = null;

export function currentRemoteBindings(): RemoteBindings {
  return current;
}

export function applyRemoteBindings(raw: unknown): void {
  const parsed = parseRemoteBindings(raw);
  if (parsed) current = parsed;
}

export function loadRemoteBindings(): Promise<void> {
  loading ??= fetch(getApiUrl("/settings/inputs"))
    .then((response) => (response.ok ? response.json() : null))
    .then((payload) => applyRemoteBindings(payload?.bindings))
    .catch((error: unknown) => {
      loading = null;
      console.warn("Table des touches du serveur indisponible, table par défaut appliquée", error);
    });
  return loading;
}
