import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";

export interface VideoWebState {
  web_issues: string[];
  web_status: "pending" | "ready" | "error" | null;
}

type T = (key: string, params?: Record<string, string | number>) => string;

export function useWebRendition(videoId: number, t: T) {
  const { libraryVersion } = usePlaybackSocket();
  const [state, setState] = useState<VideoWebState | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => fetch(getApiUrl(`/videos/${videoId}`), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setState(await res.json());
    })
    .catch(() => {}), [videoId]);

  useEffect(() => {
    void load();
  }, [load, libraryVersion]);

  useEffect(() => {
    if (state?.web_status !== "pending") return;
    const id = setInterval(() => void load(), 4000);
    return () => clearInterval(id);
  }, [state?.web_status, load]);

  const act = async (method: "POST" | "DELETE") => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch(getApiUrl(`/videos/${videoId}/web-rendition`), { method });
      if (res.ok) {
        setMessage(method === "POST" ? t("webRendition.queued") : null);
        setState((prev) => (prev ? { ...prev, web_status: method === "POST" ? "pending" : null } : prev));
      } else {
        const body = await res.json().catch(() => ({}));
        setMessage(errorMessage(body, t("webRendition.failed")));
      }
    } catch {
      setMessage(t("webRendition.failed"));
    } finally {
      setBusy(false);
    }
  };

  return { state, busy, message, act };
}

export function decodeIssueLabels(issues: string[], t: T): string[] {
  return issues.filter((issue) => issue.startsWith("decode:")).map((issue) =>
    issue === "decode:pixel-format"
      ? t("webRendition.issuePixel")
      : t("webRendition.issueCodec", { codec: issue.replace("decode:codec-", "").toUpperCase() }),
  );
}
