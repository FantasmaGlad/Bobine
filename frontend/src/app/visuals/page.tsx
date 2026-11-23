"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import PageNav from "@/components/PageNav";
import type { BackgroundItem } from "@/components/backgrounds/types";
import LoopEditor from "@/components/signage/LoopEditor";
import { useSignageLoop, type SignageDraft } from "@/components/signage/useSignageLoop";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { moved } from "@/lib/signageLoop";
import { oneOf } from "@/lib/urlView";
import { useUrlView } from "@/lib/useUrlView";
import { useToast } from "@/lib/useToast";

const CHANNELS = oneOf(["cable", "network"] as const, "cable");

function useBackgrounds(): BackgroundItem[] {
  const [backgrounds, setBackgrounds] = useState<BackgroundItem[]>([]);
  useEffect(() => {
    fetch(getApiUrl("/backgrounds"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then((list: BackgroundItem[]) => setBackgrounds(list))
      .catch((error) => console.warn("Fonds illisibles", error));
  }, []);
  return backgrounds;
}

export default function VisualsPage() {
  const { t } = useAppSettings();
  const [channel, setChannel] = useUrlView("channel", CHANNELS);
  const { entries, failed, save } = useSignageLoop(channel);
  const backgrounds = useBackgrounds();
  const { toast, showToast } = useToast();
  const drafts: SignageDraft[] = (entries ?? []).map(({ background_id, seconds }) => ({ background_id, seconds }));
  const commit = async (next: SignageDraft[]) => {
    if (!(await save(next))) showToast(t("signage.saveError"), "error");
  };

  return (
    <div className="library-container signage-page">
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      <PageNav
        tabs={[{ id: "cable", label: t("signage.cable"), icon: "cable" }, { id: "network", label: t("signage.network"), icon: "wifi" }]}
        value={channel}
        onChange={(id) => setChannel(CHANNELS(id))}
        ariaLabel={t("signage.channelsLabel")}
        actions={(
          <a href={`/signage/?channel=${channel}`} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
            <Icon name="open_in_new" size={16} />
            {t("signage.openScreen")}
          </a>
        )}
      />
      {failed && <div className="live-empty">{t("signage.loadError")}</div>}
      {entries && (
        <LoopEditor
          entries={entries}
          backgrounds={backgrounds}
          t={t}
          onMove={(from, to) => void commit(moved(drafts, from, to))}
          onSeconds={(index, seconds) => void commit(drafts.map((d, i) => (i === index ? { ...d, seconds } : d)))}
          onRemove={(index) => void commit(drafts.filter((_, i) => i !== index))}
          onAdd={(backgroundId) => void commit([...drafts, { background_id: backgroundId, seconds: null }])}
        />
      )}
    </div>
  );
}
