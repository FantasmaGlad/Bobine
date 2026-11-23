"use client";

import Icon from "@/components/Icon";
import LoopEditor from "@/components/signage/LoopEditor";
import { useSignageLoop, type SignageDraft } from "@/components/signage/useSignageLoop";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { DisplayChannel } from "@/lib/displayChannel";
import { moved } from "@/lib/signageLoop";
import { useToast } from "@/lib/useToast";
import type { BackgroundSummary } from "./types";

export default function SignagePanel({ channel, backgrounds }: { channel: DisplayChannel; backgrounds: BackgroundSummary[] }) {
  const { t } = useAppSettings();
  const { entries, failed, save } = useSignageLoop(channel);
  const { toast, showToast } = useToast();
  const drafts: SignageDraft[] = (entries ?? []).map(({ background_id, seconds }) => ({ background_id, seconds }));
  const commit = async (next: SignageDraft[]) => {
    if (!(await save(next))) showToast(t("signage.saveError"), "error");
  };

  return (
    <>
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      <p className="signage-lock">
        <Icon name="slideshow" size={18} />
        {t("dashboard.signageNotice")}
      </p>
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
    </>
  );
}
