import { errorMessage } from "./apiError.ts";
import { backoffMs, retryNotice, type UploadNotice, type UploadPhase } from "./uploadFlow.ts";

export const MAX_ATTEMPTS = 8;
export const SESSION_TIMEOUT_MS = 15_000;
export const OFFSET_TIMEOUT_MS = 10_000;
export const CHUNK_STALL_TIMEOUT_MS = 30_000;
export const CHUNK_TIMEOUT_MS = 2 * 60 * 1000;

export class ChunkedUnsupportedError extends Error {}
export class UploadAbortedError extends Error {}

export class UploadNoticeError extends Error {
  key: string;
  params: Record<string, string | number>;
  fatal: boolean;
  constructor(key: string, message: string, params: Record<string, string | number> = {}, fatal = false) {
    super(message);
    this.key = key;
    this.params = params;
    this.fatal = fatal;
  }
}

interface SessionState {
  upload_id: string;
  offset: number;
  size: number;
  complete: boolean;
  chunk_size: number;
}

type ChunkResult = { status: number; offset: number; detail?: string };
type SendChunkFn = (
  uploadId: string,
  file: File,
  offset: number,
  end: number,
  opts: ChunkedUploadOptions,
  onBytes: (sent: number) => void,
) => Promise<ChunkResult>;

export interface ChunkedUploadOptions {
  apiUrl: (path: string) => string;
  onProgress: (loaded: number, total: number) => void;
  signal: AbortSignal;
  onSession?: (uploadId: string) => void;
  onPhase?: (phase: UploadPhase) => void;
  onNotice?: (notice: UploadNotice | null) => void;
  deps?: {
    fetchImpl?: typeof fetch;
    sendChunkImpl?: SendChunkFn;
    sleepImpl?: (ms: number, signal: AbortSignal) => Promise<void>;
  };
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

async function withTimeout<T>(
  signal: AbortSignal,
  timeoutMs: number,
  run: (signal: AbortSignal) => Promise<T>,
): Promise<T> {
  if (signal.aborted) throw new UploadAbortedError();
  const inner = new AbortController();
  let timedOut = false;
  const onAbort = () => inner.abort();
  signal.addEventListener("abort", onAbort, { once: true });
  const timer = setTimeout(() => { timedOut = true; inner.abort(); }, timeoutMs);
  try {
    return await run(inner.signal);
  } catch (err) {
    if (signal.aborted) throw new UploadAbortedError();
    if (timedOut) {
      throw new UploadNoticeError("uploads.reason.timeout", `Délai dépassé (${Math.round(timeoutMs / 1000)} s)`, { seconds: Math.round(timeoutMs / 1000) });
    }
    throw err;
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", onAbort);
  }
}

function asUnreachable(err: unknown): unknown {
  if (err instanceof UploadAbortedError || err instanceof UploadNoticeError || err instanceof ChunkedUnsupportedError) return err;
  if ((err as { fatal?: boolean })?.fatal) return err;
  if (err instanceof TypeError) {
    return new UploadNoticeError("uploads.reason.network", "Erreur réseau");
  }
  return err;
}

async function createSession(file: File, opts: ChunkedUploadOptions): Promise<SessionState> {
  const fetchImpl = opts.deps?.fetchImpl ?? fetch;
  try {
    return await withTimeout(opts.signal, SESSION_TIMEOUT_MS, async (signal) => {
      const res = await fetchImpl(opts.apiUrl("/uploads"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, size: file.size, fingerprint: fileFingerprint(file) }),
        signal,
      });
      if (res.status === 404 || res.status === 405) throw new ChunkedUnsupportedError();
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw Object.assign(new Error(errorMessage(body, `Erreur serveur (${res.status})`)), { fatal: true });
      }
      return (await res.json()) as SessionState;
    });
  } catch (err) {
    const mapped = asUnreachable(err);
    if (mapped instanceof UploadNoticeError && !mapped.fatal) {
      if (mapped.key === "uploads.reason.timeout") {
        throw new UploadNoticeError("uploads.errors.sessionTimeout", `Le serveur ne répond pas (aucune réponse après ${SESSION_TIMEOUT_MS / 1000} s). Vérifiez que Bobine est démarré, puis réessayez.`, { seconds: SESSION_TIMEOUT_MS / 1000 }, true);
      }
      throw new UploadNoticeError("uploads.errors.unreachable", "Impossible de joindre le serveur. Vérifiez que Bobine est démarré et la connexion réseau, puis réessayez.", {}, true);
    }
    throw mapped;
  }
}

async function fetchOffset(uploadId: string, opts: ChunkedUploadOptions): Promise<number> {
  const fetchImpl = opts.deps?.fetchImpl ?? fetch;
  return withTimeout(opts.signal, OFFSET_TIMEOUT_MS, async (signal) => {
    const res = await fetchImpl(opts.apiUrl(`/uploads/${uploadId}`), { cache: "no-store", signal });
    if (!res.ok) throw Object.assign(new Error(`Session de transfert perdue (${res.status})`), { sessionLost: res.status === 404 });
    return (await res.json()).offset as number;
  });
}

const sendChunk: SendChunkFn = (uploadId, file, offset, end, opts, onBytes) => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let stallTimer: ReturnType<typeof setTimeout> | undefined;
    const clearStall = () => { if (stallTimer !== undefined) clearTimeout(stallTimer); stallTimer = undefined; };
    const armStall = () => {
      clearStall();
      stallTimer = setTimeout(() => {
        cleanup();
        xhr.abort();
        reject(new UploadNoticeError("uploads.reason.stalled", "Aucune donnée transmise", { seconds: CHUNK_STALL_TIMEOUT_MS / 1000 }));
      }, CHUNK_STALL_TIMEOUT_MS);
    };
    const onAbort = () => { clearStall(); xhr.abort(); reject(new UploadAbortedError()); };
    opts.signal.addEventListener("abort", onAbort, { once: true });
    const cleanup = () => { clearStall(); opts.signal.removeEventListener("abort", onAbort); };

    xhr.open("PATCH", opts.apiUrl(`/uploads/${uploadId}`));
    xhr.timeout = CHUNK_TIMEOUT_MS;
    xhr.setRequestHeader("Upload-Offset", String(offset));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.addEventListener("progress", (e) => { armStall(); if (e.lengthComputable) onBytes(e.loaded); });
    xhr.addEventListener("load", () => {
      cleanup();
      let body: { offset?: number; detail?: string } = {};
      try { body = JSON.parse(xhr.responseText); } catch { }
      resolve({ status: xhr.status, offset: typeof body.offset === "number" ? body.offset : offset, detail: body.detail });
    });
    xhr.addEventListener("error", () => { cleanup(); reject(new UploadNoticeError("uploads.reason.network", "Erreur réseau")); });
    xhr.addEventListener("timeout", () => { cleanup(); reject(new UploadNoticeError("uploads.reason.timeout", "Délai dépassé", { seconds: CHUNK_TIMEOUT_MS / 1000 })); });
    armStall();
    xhr.send(file.slice(offset, end));
  });
};

function failureReason(err: unknown): { reasonKey: string; status?: number; seconds?: number } {
  if (err instanceof UploadNoticeError && err.key.startsWith("uploads.reason.")) {
    const seconds = err.params.seconds;
    return { reasonKey: err.key, ...(typeof seconds === "number" ? { seconds } : {}) };
  }
  const status = (err as { status?: number }).status;
  if (typeof status === "number") return { reasonKey: "uploads.reason.server", status };
  return { reasonKey: "uploads.reason.network" };
}

export async function uploadFileInChunks(file: File, opts: ChunkedUploadOptions): Promise<string> {
  const sleepImpl = opts.deps?.sleepImpl ?? sleep;
  const sendImpl = opts.deps?.sendChunkImpl ?? sendChunk;
  opts.onPhase?.("connecting");
  const session = await createSession(file, opts);
  opts.onSession?.(session.upload_id);
  opts.onPhase?.("sending");
  const chunkSize = Math.max(1, session.chunk_size);
  let offset = session.offset;
  opts.onProgress(offset, file.size);

  let failures = 0;
  while (offset < file.size) {
    const end = Math.min(file.size, offset + chunkSize);
    const attemptStart = offset;
    try {
      const result = await sendImpl(session.upload_id, file, offset, end, opts, (sent) => opts.onProgress(offset + sent, file.size));
      if (result.status === 200) {
        offset = result.offset;
        failures = 0;
        opts.onNotice?.(null);
        opts.onProgress(offset, file.size);
        continue;
      }
      if (result.status === 409) {
        offset = result.offset;
        opts.onProgress(offset, file.size);
        continue;
      }
      if (result.status >= 400 && result.status < 500) {
        throw Object.assign(new Error(errorMessage(result, `Refusé par le serveur (${result.status})`)), { fatal: true });
      }
      throw Object.assign(new Error(`Erreur serveur (${result.status})`), { status: result.status });
    } catch (err) {
      if (err instanceof UploadAbortedError || (err as { fatal?: boolean }).fatal) throw err;
      failures += 1;
      const reason = failureReason(err);
      if (failures >= MAX_ATTEMPTS) {
        throw new UploadNoticeError(
          "uploads.errors.interrupted",
          `Transfert interrompu après ${MAX_ATTEMPTS} tentatives : ${(err as Error).message}`,
          {
            max: MAX_ATTEMPTS,
            reasonKey: reason.reasonKey,
            ...(reason.status !== undefined ? { status: reason.status } : {}),
            ...(reason.seconds !== undefined ? { seconds: reason.seconds } : {}),
          },
          true,
        );
      }
      opts.onNotice?.(retryNotice(failures + 1, MAX_ATTEMPTS, reason.reasonKey, reason.status));
      await sleepImpl(backoffMs(failures), opts.signal);
      try {
        const synced = await fetchOffset(session.upload_id, opts);
        if (synced > attemptStart) failures = 0;
        offset = synced;
        opts.onProgress(offset, file.size);
      } catch (syncErr) {
        if (syncErr instanceof UploadAbortedError || (syncErr as DOMException).name === "AbortError") throw new UploadAbortedError();
        if ((syncErr as { sessionLost?: boolean }).sessionLost) {
          throw new UploadNoticeError("uploads.errors.sessionLost", "Session de transfert perdue (le serveur a redémarré ou la session a expiré). Relancez l'import.", {}, true);
        }
      }
    }
  }
  opts.onNotice?.(null);
  return session.upload_id;
}

export async function cancelChunkedUpload(uploadId: string, apiUrl: (path: string) => string): Promise<void> {
  try {
    await fetch(apiUrl(`/uploads/${uploadId}`), { method: "DELETE", keepalive: true });
  } catch {
  }
}
