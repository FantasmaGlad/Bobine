"use client";

import { useCallback, useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import {
  isLockedByEnvironment,
  parseMediaNativeStatus,
  stateKey,
  type MediaNativeStatus,
} from "@/lib/mediaNative";

function getApiUrl(path: string): string {
  if (typeof window !== "undefined" && window.location.port === "3000") return `http://localhost:8001/api${path}`;
  return `/api${path}`;
}

/**
 * Réglages → Composant audio natif (expérimental). Désactivé par défaut ; il n'accélère que de
 * nouveaux imports et toute erreur retombe sur le chemin habituel : aucun média n'est perdu.
 * L'état affiché (actif, repli, absent) est celui que mesure le serveur.
 */
export default function MediaNativeSetting() {
  const { t } = useAppSettings();
  const [status, setStatus] = useState<MediaNativeStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl("/settings/media-native"), { cache: "no-store" });
      setStatus(res.ok ? parseMediaNativeStatus(await res.json()) : null);
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture initiale de l'état réel côté serveur
    void refresh();
  }, [refresh]);

  const toggle = async (checked: boolean) => {
    setBusy(true);
    setFailed(false);
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ media_native: checked ? "true" : "false" }),
      });
      if (!res.ok) setFailed(true);
    } catch {
      setFailed(true);
    } finally {
      await refresh();
      setBusy(false);
    }
  };

  const locked = isLockedByEnvironment(status);
  const checked = status ? status.setting : false;
  const key = stateKey(status);

  return (
    <section className="live-block" id="media-native-section">
      <h3>
        <Icon name="bolt" size={18} /> {t("mediaNative.section")}
      </h3>
      <p className="settings-hint" style={{ marginTop: 0 }}>{t("mediaNative.hint")}</p>
      <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="checkbox"
          checked={checked}
          disabled={busy || locked || status === null}
          onChange={(e) => toggle(e.target.checked)}
        />
        {t("mediaNative.label")}
      </label>
      <p className="settings-hint" role="status" data-testid="media-native-state">
        {t(`mediaNative.${key}`)}
        {status?.state === "active" && status.binary_version ? ` (v${status.binary_version})` : ""}
      </p>
      {locked && (
        <p className="settings-hint">
          {t(status?.forced_by_env ? "mediaNative.forcedOn" : "mediaNative.forcedOff")}
        </p>
      )}
      {failed && <p className="settings-hint" style={{ color: "var(--accent-danger)" }}>{t("mediaNative.saveError")}</p>}
    </section>
  );
}
