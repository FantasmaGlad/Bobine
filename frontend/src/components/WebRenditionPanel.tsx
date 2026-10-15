"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";

interface VideoWebState {
  web_issues: string[];
  web_status: "pending" | "ready" | "error" | null;
}

function getApiUrl(path: string): string {
  if (typeof window !== "undefined" && window.location.port === "3000") return `http://localhost:8001/api${path}`;
  return `/api${path}`;
}

/** Raisons de non-lisibilité susceptibles d'empêcher le décodage (préfixe
 *  `decode:`, cf. backend `app/utils/web_profile.py`) — les notes de
 *  performance (`perf:*`) n'appellent pas de version compatible. */
function decodeIssues(issues: string[]): string[] {
  return issues.filter((issue) => issue.startsWith("decode:"));
}

/**
 * Panneau « version compatible navigateurs » du détail d'une vidéo : n'apparaît que pour un
 * fichier qu'un navigateur tiers pourrait ne pas savoir décoder. L'original n'est jamais
 * modifié ; la version compatible est servie automatiquement aux clients qui
 * en ont besoin (négociation `?accept=`, cf. lib/clientCodecSupport.ts).
 */
export default function WebRenditionPanel({ videoId }: { videoId: number }) {
  const { t } = useAppSettings();
  const { libraryVersion } = usePlaybackSocket();
  const [state, setState] = useState<VideoWebState | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl(`/videos/${videoId}`), { cache: "no-store" });
      if (res.ok) setState(await res.json());
    } catch {
      // réseau indisponible : l'état affiché reste celui du dernier succès
    }
  }, [videoId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture ponctuelle d'une API externe, déclenchée aussi par library_change
    void load();
  }, [load, libraryVersion]);

  // Production en cours : l'évènement WebSocket library_change prévient à la
  // fin, ce sondage léger couvre un évènement manqué (onglet masqué, coupure).
  useEffect(() => {
    if (state?.web_status !== "pending") return;
    const id = setInterval(() => void load(), 4000);
    return () => clearInterval(id);
  }, [state?.web_status, load]);

  const decode = decodeIssues(state?.web_issues ?? []);
  if (!state || decode.length === 0) return null;

  const labels = decode.map((issue) =>
    issue === "decode:pixel-format"
      ? t("webRendition.issuePixel")
      : t("webRendition.issueCodec", { codec: issue.replace("decode:codec-", "").toUpperCase() }),
  );

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
        setMessage(body.detail || t("webRendition.failed"));
      }
    } catch {
      setMessage(t("webRendition.failed"));
    } finally {
      setBusy(false);
    }
  };

  const status = state.web_status;
  return (
    <div className="web-rendition-panel" style={{ marginTop: 12, padding: "12px 14px", border: "1px solid var(--border-color)", borderRadius: "var(--radius-md)", background: "var(--bg-surface-elevated)", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
        <Icon name={status === "ready" ? "check_circle" : "devices"} size={18} color={status === "ready" ? "var(--accent-success)" : "var(--accent-primary)"} />
        {t("webRendition.title")}
      </div>
      <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
        {status === "ready" ? t("webRendition.ready") : t("webRendition.notSafe", { issues: labels.join(", ") })}
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {status === "ready" ? (
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => act("DELETE")}>
            {t("webRendition.remove")}
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-sm" disabled={busy || status === "pending"} onClick={() => act("POST")}>
            {status === "pending" ? (
              <>
                <Icon name="sync" size={14} className="olc-spin" /> {t("webRendition.creating")}
              </>
            ) : (
              t("webRendition.create")
            )}
          </button>
        )}
        {status === "error" && <span style={{ color: "var(--accent-error)", fontSize: "0.8rem" }}>{t("webRendition.failed")}</span>}
        {message && <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{message}</span>}
      </div>
    </div>
  );
}
