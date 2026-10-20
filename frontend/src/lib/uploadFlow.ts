/**
 * Logique pure (sans React ni réseau) du suivi d'un import : phases affichées,
 * messages d'état traduisibles, détection d'une tâche serveur perdue.
 *
 * Pourquoi ce module : jusqu'ici, un serveur qui ne répondait plus laissait
 * l'interface à 0 % sans aucune explication (création de session sans délai,
 * reprises invisibles, tâche introuvable ignorée en silence). Ces règles sont
 * isolées ici pour être testées sans navigateur (`tests/uploadFlow.test.ts`) ;
 * `lib/chunkedUpload.ts` et `lib/UploadManager.tsx` ne font que les appliquer.
 */

/** Étape visible d'un import : connexion (création de la session d'envoi),
 *  envoi des morceaux, traitement côté serveur. */
export type UploadPhase = "connecting" | "sending" | "processing";

/** Message d'état traduisible : une clé i18n + ses paramètres. Les erreurs
 *  renvoyées par le serveur (`detail`) restent du texte brut, sans clé. */
export interface UploadNotice {
  key: string;
  params?: Record<string, string | number>;
}

/** Nombre de sondages CONSÉCUTIFS réussis (réponse 200) où la tâche est absente
 *  de `GET /api/import-jobs` avant de la déclarer perdue. À 1,5 s d'intervalle :
 *  ~6 s, assez pour ne pas réagir à une réponse isolée, assez court pour ne
 *  pas laisser l'utilisateur attendre sans rien voir. */
export const JOB_MISS_LIMIT = 4;

/** Sondages consécutifs en échec (serveur injoignable) avant d'afficher que le
 *  serveur ne répond plus. */
export const POLL_FAILURE_LIMIT = 3;

/** Nouveau compteur d'absences : remis à zéro dès que la tâche est revue. */
export function nextMissCount(previous: number | undefined, found: boolean): number {
  return found ? 0 : (previous ?? 0) + 1;
}

export function isJobLost(misses: number, limit: number = JOB_MISS_LIMIT): boolean {
  return misses >= limit;
}

/** Compteur de sondages en échec consécutifs. */
export function nextPollFailures(previous: number, ok: boolean): number {
  return ok ? 0 : previous + 1;
}

export function isServerSilent(failures: number, limit: number = POLL_FAILURE_LIMIT): boolean {
  return failures >= limit;
}

/** Clé i18n du libellé de phase. */
export function phaseLabelKey(phase: UploadPhase): string {
  return `uploads.phase.${phase}`;
}

export type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

/**
 * Texte d'un message d'état. Tout paramètre dont le nom finit par `Key`
 * (`reasonKey`, `hintKey`…) est une clé i18n : elle est traduite d'abord puis
 * injectée sous le même nom sans le suffixe (`{{reason}}`, `{{hint}}`). Permet
 * « Transfert interrompu après 8 tentatives ({{reason}}) » sans figer la
 * raison dans une seule langue.
 */
export function formatNotice(t: TranslateFn, notice: UploadNotice): string {
  const params: Record<string, string | number> = { ...(notice.params ?? {}) };
  for (const name of Object.keys(params)) {
    const value = params[name];
    if (name.endsWith("Key") && typeof value === "string") {
      params[name.slice(0, -3)] = t(value, params);
      delete params[name];
    }
  }
  return t(notice.key, params);
}

/** Erreur d'une tâche serveur (`error_code` / `error_params` de
 *  `GET /api/import-jobs`) → message traduisible ; `undefined` si le code est
 *  inconnu (on affiche alors le texte du serveur tel quel). */
export function jobErrorNotice(code: string | null | undefined, params: Record<string, unknown> | null | undefined): UploadNotice | undefined {
  if (code === "media_tool_missing") {
    const tool = typeof params?.tool === "string" ? params.tool : "ffmpeg";
    const os = typeof params?.os === "string" && ["macos", "windows", "linux", "android"].includes(params.os) ? params.os : "linux";
    return { key: "uploads.errors.mediaToolMissing", params: { tool, hintKey: `uploads.errors.installHint.${os}` } };
  }
  return undefined;
}

/** Message affiché pendant l'attente avant une nouvelle tentative. */
export function retryNotice(attempt: number, max: number, reasonKey: string, status?: number): UploadNotice {
  if (reasonKey === "uploads.reason.server") {
    return { key: "uploads.retryingServerError", params: { attempt, max, status: status ?? 0 } };
  }
  return { key: "uploads.retrying", params: { attempt, max } };
}

/** Attente avant la tentative suivante : 1 s, 2 s, 4 s, 8 s puis 15 s au plus. */
export function backoffMs(failures: number): number {
  return Math.min(15000, 1000 * 2 ** (Math.max(1, failures) - 1));
}
