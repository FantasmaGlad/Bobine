/**
 * Client du téléversement par morceaux reprenable (backend :
 * `app/utils/staged_uploads.py`, `app/routers/uploads.py`).
 *
 * Remplace, pour les gros fichiers (vidéos, fonds, archives ZIP), l'unique
 * requête `multipart/form-data` de plusieurs Go : le fichier est découpé
 * (`Blob.slice`, le navigateur ne charge jamais tout en mémoire), envoyé
 * morceau par morceau, et REPREND à l'octet près après une coupure réseau —
 * ou après un rechargement de page si le même fichier est re-sélectionné
 * (empreinte nom|taille|date). Progression par `XMLHttpRequest` : l'API
 * `fetch` n'expose pas la progression d'envoi sous Firefox.
 */

const MAX_ATTEMPTS = 8;
const CHUNK_TIMEOUT_MS = 5 * 60 * 1000;

export class ChunkedUnsupportedError extends Error {}
export class UploadAbortedError extends Error {}

interface SessionState {
  upload_id: string;
  offset: number;
  size: number;
  complete: boolean;
  chunk_size: number;
}

export interface ChunkedUploadOptions {
  apiUrl: (path: string) => string;
  /** Octets déjà confirmés ou en cours d'envoi, sur le total du fichier. */
  onProgress: (loaded: number, total: number) => void;
  signal: AbortSignal;
  /** Prévient quand la session serveur existe (permet l'annulation propre). */
  onSession?: (uploadId: string) => void;
}

export function fileFingerprint(file: File): string {
  return `${file.name}|${file.size}|${file.lastModified}`;
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new UploadAbortedError());
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => { clearTimeout(timer); reject(new UploadAbortedError()); }, { once: true });
  });
}

async function createSession(file: File, opts: ChunkedUploadOptions): Promise<SessionState> {
  const res = await fetch(opts.apiUrl("/uploads"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, size: file.size, fingerprint: fileFingerprint(file) }),
    signal: opts.signal,
  });
  if (res.status === 404 || res.status === 405) throw new ChunkedUnsupportedError();
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Erreur serveur (${res.status})`);
  }
  return res.json();
}

async function fetchOffset(uploadId: string, opts: ChunkedUploadOptions): Promise<number> {
  const res = await fetch(opts.apiUrl(`/uploads/${uploadId}`), { cache: "no-store", signal: opts.signal });
  if (!res.ok) throw new Error(`Session de transfert perdue (${res.status})`);
  return (await res.json()).offset;
}

/** Envoie un morceau ; renvoie l'offset confirmé par le serveur. */
function sendChunk(
  uploadId: string,
  file: File,
  offset: number,
  end: number,
  opts: ChunkedUploadOptions,
  onBytes: (sent: number) => void,
): Promise<{ status: number; offset: number; detail?: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const onAbort = () => { xhr.abort(); reject(new UploadAbortedError()); };
    opts.signal.addEventListener("abort", onAbort, { once: true });
    const cleanup = () => opts.signal.removeEventListener("abort", onAbort);

    xhr.open("PATCH", opts.apiUrl(`/uploads/${uploadId}`));
    xhr.timeout = CHUNK_TIMEOUT_MS;
    xhr.setRequestHeader("Upload-Offset", String(offset));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.addEventListener("progress", (e) => { if (e.lengthComputable) onBytes(e.loaded); });
    xhr.addEventListener("load", () => {
      cleanup();
      let body: { offset?: number; detail?: string } = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* corps non JSON */ }
      resolve({ status: xhr.status, offset: typeof body.offset === "number" ? body.offset : offset, detail: body.detail });
    });
    xhr.addEventListener("error", () => { cleanup(); reject(new Error("Erreur réseau")); });
    xhr.addEventListener("timeout", () => { cleanup(); reject(new Error("Délai dépassé")); });
    xhr.send(file.slice(offset, end));
  });
}

/**
 * Téléverse `file` par morceaux et renvoie l'identifiant de session, à passer
 * au point d'entrée d'import (`upload_id`). Reprend automatiquement après
 * toute erreur réseau (jusqu'à MAX_ATTEMPTS tentatives consécutives sans
 * progrès, attente croissante) ; relève `ChunkedUnsupportedError` si le
 * serveur ne connaît pas ce protocole (ancienne version) pour que l'appelant
 * retombe sur l'envoi classique.
 */
export async function uploadFileInChunks(file: File, opts: ChunkedUploadOptions): Promise<string> {
  const session = await createSession(file, opts);
  opts.onSession?.(session.upload_id);
  const chunkSize = Math.max(1, session.chunk_size);
  let offset = session.offset;
  opts.onProgress(offset, file.size);

  let failures = 0;
  while (offset < file.size) {
    const end = Math.min(file.size, offset + chunkSize);
    try {
      const result = await sendChunk(session.upload_id, file, offset, end, opts, (sent) => opts.onProgress(offset + sent, file.size));
      if (result.status === 200) {
        offset = result.offset;
        failures = 0;
        opts.onProgress(offset, file.size);
        continue;
      }
      if (result.status === 409) {
        // Désynchronisé (réponse perdue lors d'une reprise) : le serveur donne l'offset réel.
        offset = result.offset;
        opts.onProgress(offset, file.size);
        continue;
      }
      if (result.status >= 400 && result.status < 500) {
        // Refus définitif (507 disque plein, 413, 404 session expirée…) : inutile de réessayer.
        throw Object.assign(new Error(result.detail || `Refusé par le serveur (${result.status})`), { fatal: true });
      }
      throw new Error(`Erreur serveur (${result.status})`);
    } catch (err) {
      if (err instanceof UploadAbortedError || (err as { fatal?: boolean }).fatal) throw err;
      failures += 1;
      if (failures >= MAX_ATTEMPTS) throw new Error(`Transfert interrompu après ${MAX_ATTEMPTS} tentatives : ${(err as Error).message}`);
      await sleep(Math.min(15000, 1000 * 2 ** (failures - 1)), opts.signal);
      try {
        offset = await fetchOffset(session.upload_id, opts);
        opts.onProgress(offset, file.size);
      } catch (syncErr) {
        if (syncErr instanceof UploadAbortedError || (syncErr as DOMException).name === "AbortError") throw new UploadAbortedError();
        // serveur injoignable : la boucle réessaiera après la prochaine attente
      }
    }
  }
  return session.upload_id;
}

export async function cancelChunkedUpload(uploadId: string, apiUrl: (path: string) => string): Promise<void> {
  try {
    await fetch(apiUrl(`/uploads/${uploadId}`), { method: "DELETE", keepalive: true });
  } catch {
    // best-effort : le serveur purge de toute façon les sessions de plus de 24 h
  }
}
