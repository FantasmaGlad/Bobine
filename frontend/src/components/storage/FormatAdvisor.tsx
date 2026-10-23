"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import SegmentedTabs from "@/components/SegmentedTabs";
import Sheet from "@/components/Sheet";
import { adviceQuery, fsLabel, OS_CHOICES, storageRequest, visibleNotes, type FormatAdvice, type OsChoice } from "@/lib/storageApi";
import { storageErrorText, tr, type StorageCtx } from "./common";

interface Props extends StorageCtx {
  open: boolean;
  onClose: () => void;
}

/** Conseiller de format : selon l'OS de Bobine et ceux qui brancheront le support. Décrit, n'exécute jamais rien. */
export default function FormatAdvisor({ open, onClose, t, lang, notify }: Props) {
  const [host, setHost] = useState<OsChoice>("linux");
  const [others, setOthers] = useState<OsChoice[]>([]);
  const [media, setMedia] = useState<"flash" | "ssd" | "hdd">("flash");
  const [legacy, setLegacy] = useState(false);
  const [advice, setAdvice] = useState<FormatAdvice | null>(null);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    void storageRequest<FormatAdvice>(`/advisor/format${adviceQuery(host, others, media, legacy)}`).then((result) => {
      if (!alive) return;
      if (result.ok) setAdvice(result.data);
      else notify(storageErrorText(result.error, t, lang), "error");
    });
    return () => {
      alive = false;
    };
  }, [open, host, others, media, legacy, notify, t, lang]);

  const toggleOther = (os: OsChoice) => setOthers((prev) => (prev.includes(os) ? prev.filter((o) => o !== os) : [...prev, os]));
  const osLabel = (os: string) => t(`storage.advisor.oses.${os}`);

  return (
    <Sheet open={open} onClose={onClose} title={t("storage.details.formatAdvice")} closeLabel={t("storage.close")} tall>
      <div className="dv-detail">
        <div className="dv-detail-block">
          <h4>{t("storage.advisor.host")}</h4>
          <SegmentedTabs ariaLabel={t("storage.advisor.host")} value={host} onChange={(id) => setHost(id as OsChoice)} tabs={OS_CHOICES.map((os) => ({ id: os, label: osLabel(os) }))} />
        </div>
        <div className="dv-detail-block">
          <h4>{t("storage.advisor.others")}</h4>
          <div className="st-choices">
            {OS_CHOICES.filter((os) => os !== host).map((os) => (
              <label key={os} className="st-check st-check--chip">
                <input type="checkbox" checked={others.includes(os)} onChange={() => toggleOther(os)} />
                <span>{osLabel(os)}</span>
              </label>
            ))}
            <label className="st-check st-check--chip">
              <input type="checkbox" checked={legacy} onChange={(e) => setLegacy(e.target.checked)} />
              <span>{t("storage.advisor.legacy")}</span>
            </label>
          </div>
        </div>
        <div className="dv-detail-block">
          <h4>{t("storage.advisor.media")}</h4>
          <SegmentedTabs
            ariaLabel={t("storage.advisor.media")}
            value={media}
            onChange={(id) => setMedia(id as "flash" | "ssd" | "hdd")}
            tabs={(["flash", "ssd", "hdd"] as const).map((m) => ({ id: m, label: t(`storage.advisor.medias.${m}`) }))}
          />
        </div>

        {advice && (
          <div className="dv-note dv-note--strong" role="status">
            <Icon name="check_circle" size={20} />
            <span>
              <strong>{t("storage.advisor.result", { fs: fsLabel(advice.fstype) })}</strong>
              <br />
              {tr(t, `storage.fsReasons.${advice.reason}`)}
              {visibleNotes(advice).length > 0 && (
                <>
                  <br />
                  <span className="dv-sub">{visibleNotes(advice).map((n) => tr(t, `storage.fsNotes.${n}`)).filter(Boolean).join(" · ")}</span>
                </>
              )}
            </span>
          </div>
        )}
        {advice && [advice.host_os, ...advice.other_oses].filter((os) => advice.procedures[os]).map((os) => (
          <div key={os} className="dv-detail-block">
            <h4>{t("storage.advisor.steps", { os: osLabel(os) })}</h4>
            <ul className="st-steps">
              {advice.procedures[os].map((step) => <li key={step}><code>{step}</code></li>)}
            </ul>
          </div>
        ))}
        <p className="dv-sub"><Icon name="info" size={14} /> {t("storage.advisor.erases")}</p>
      </div>
    </Sheet>
  );
}
