"use client";

import Icon from "@/components/Icon";
import LoopEditor from "@/components/signage/LoopEditor";
import { useSignageLoop, type SignageDraft } from "@/components/signage/useSignageLoop";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { DisplayChannel } from "@/lib/displayChannel";
import { moved } from "@/lib/signageLoop";
import { useToast } from "@/lib/useToast";
import ImportVisualsButton from "@/components/visuals/ImportVisualsButton";
import { useVisualLibrary } from "@/components/visuals/useVisualLibrary";

export default function SignagePanel({ channel }: { channel: DisplayChannel }) {
  const { t } = useAppSettings();
  const { entries, failed, save } = useSignageLoop(channel);
  const { toast, showToast } = useToast();
  const library = useVisualLibrary();
  const drafts: SignageDraft[] = (entries ?? []).map(({ visual_id, seconds }) => ({ visual_id, seconds }));
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
          visuals={library.visuals ?? []}
          importAction={<ImportVisualsButton label={t("common.import")} onFiles={library.importFiles} className="btn btn-secondary" />}
          t={t}
          onMove={(from, to) => void commit(moved(drafts, from, to))}
          onSeconds={(index, seconds) => void commit(drafts.map((d, i) => (i === index ? { ...d, seconds } : d)))}
          onRemove={(index) => void commit(drafts.filter((_, i) => i !== index))}
          onAdd={(visualId) => void commit([...drafts, { visual_id: visualId, seconds: null }])}
        />
      )}
    </>
  );
}
