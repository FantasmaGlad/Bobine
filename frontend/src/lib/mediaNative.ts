/**
 * Composant audio natif (expérimental) : lecture de l'état réel renvoyé par
 * `GET /api/settings/media-native` et choix de la clé de traduction à afficher.
 * Partie pure, sans React ni réseau, pour être testée seule.
 */
export type MediaNativeState = "disabled" | "active" | "fallback" | "absent";

export interface MediaNativeStatus {
  enabled: boolean;
  /** Valeur du réglage persisté (indépendante du forçage par l'environnement). */
  setting: boolean;
  source: "env" | "setting" | "default";
  forced_by_env: boolean | null;
  available: boolean;
  state: MediaNativeState;
  binary_version: string | null;
  formats: string[];
  reason: string | null;
}

const STATES: readonly MediaNativeState[] = ["disabled", "active", "fallback", "absent"];

/** Valide la réponse du serveur ; `null` si elle n'a pas la forme attendue. */
export function parseMediaNativeStatus(value: unknown): MediaNativeStatus | null {
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  if (!STATES.includes(v.state as MediaNativeState) || typeof v.enabled !== "boolean") return null;
  return {
    enabled: v.enabled,
    setting: v.setting === true,
    source: v.source === "env" || v.source === "setting" ? v.source : "default",
    forced_by_env: typeof v.forced_by_env === "boolean" ? v.forced_by_env : null,
    available: v.available === true,
    state: v.state as MediaNativeState,
    binary_version: typeof v.binary_version === "string" ? v.binary_version : null,
    formats: Array.isArray(v.formats) ? v.formats.filter((f): f is string => typeof f === "string") : [],
    reason: typeof v.reason === "string" ? v.reason : null,
  };
}

/** Clé i18n (sous `mediaNative.`) du texte d'état. */
export function stateKey(status: MediaNativeStatus | null): string {
  if (!status) return "stateUnknown";
  return `state_${status.state}`;
}

/**
 * Le réglage est-il modifiable ? Quand l'environnement force l'activation ou la désactivation
 * (variable BOBINE_MEDIA_NATIVE), la case reste affichée mais n'a aucun effet : on la verrouille
 * et on l'explique.
 */
export function isLockedByEnvironment(status: MediaNativeStatus | null): boolean {
  return status?.forced_by_env !== null && status?.forced_by_env !== undefined;
}
