"use client";

import React, { useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import Explorer from "@/components/storage/Explorer";
import FormatAdvisor from "@/components/storage/FormatAdvisor";
import FormatWizard from "@/components/storage/FormatWizard";
import TransferStatus from "@/components/storage/TransferStatus";
import VolumeList from "@/components/storage/VolumeList";
import VolumeSheet from "@/components/storage/VolumeSheet";
import { useStorageListing } from "@/components/storage/useStorageListing";
import { useTransferJobs } from "@/components/storage/useTransferJobs";
import { useVolumeOpeners } from "@/components/storage/useVolumeOpeners";
import { storageRequest } from "@/lib/storage/request";
import { type FormatJob } from "@/lib/storage/format";
import { useStorageEvents } from "@/lib/useStorageEvents";
import { useToast } from "@/lib/useToast";

export default function StoragePage() {
  const { t, language } = useAppSettings();
  const lang = language === "en" ? "en" : "fr";
  const { toast, showToast: notify } = useToast(5000);
  const { status, loadError, listing, portable, reload } = useStorageListing(t, lang, notify);
  const { opening, explorer, setExplorer, openVolume, openPortable } = useVolumeOpeners(t, lang, notify, reload);
  const [sheetKey, setSheetKey] = useState<string | null>(null);
  const [advisor, setAdvisor] = useState(false);
  const [formatTarget, setFormatTarget] = useState<{ key: string; name: string; resume?: FormatJob | null } | null>(null);
  const { jobIds, modes, onJob } = useTransferJobs();

  useEffect(() => {
    if (!status) return;
    void storageRequest<{ job: FormatJob | null }>("/format/active").then((result) => {
      if (result.ok && result.data.job) setFormatTarget({ key: result.data.job.job_id, name: result.data.job.label, resume: result.data.job });
    });
  }, [status]);

  useStorageEvents((event) => { if (event.scope !== "jobs") void reload(); }, !!status);

  if (loadError && !status) return <div className="rl-center-note">{t("storage.errors.network")}</div>;
  if (!status) return <div className="rl-center-note">{t("storage.loading")}</div>;

  const volumes = listing?.volumes ?? [];
  const current = explorer?.volume ? volumes.find((v) => v.key === explorer.key) ?? explorer.volume : null;
  const sheetVolume = volumes.find((v) => v.key === sheetKey) ?? null;
  const ctx = { t, lang: lang as "fr" | "en", notify };
  const showJobs = jobIds.length > 0;

  return (
    <div className="radio-lib radio-lib--tabs dv-page st-page">
      {toast && <div className={`toast ${toast.type}`} role="status"><span>{toast.message}</span></div>}

      <main className="radio-lib-main">
        {explorer ? (
          <>
            <Explorer
              {...ctx}
              volumeKey={explorer.key}
              name={explorer.name}
              portable={explorer.portable}
              canExtend={!!current && current.uuid_known}
              registered={!!current?.library?.registered}
              onClose={() => setExplorer(null)}
              onJob={onJob}
              onLibraryChanged={() => void reload()}
            />
            {showJobs && <TransferStatus {...ctx} jobIds={jobIds} modes={modes} onDone={() => void reload()} />}
          </>
        ) : (
          <div className="dv-section">
            {showJobs && <TransferStatus {...ctx} jobIds={jobIds} modes={modes} onDone={() => void reload()} />}
            <VolumeList ctx={ctx} listing={listing} portable={portable} opening={opening} onExplore={openVolume} onMore={setSheetKey} onOpenPortable={openPortable} />
            <div className="dv-quiet-actions">
              <button type="button" className="dv-link-btn" onClick={() => setAdvisor(true)}><Icon name="help" size={14} /> {t("storage.details.formatAdvice")}</button>
              <button type="button" className="dv-link-btn" onClick={() => void reload()}><Icon name="refresh" size={14} /> {t("storage.refresh")}</button>
            </div>
          </div>
        )}
      </main>

      <VolumeSheet
        {...ctx}
        volume={sheetVolume}
        onClose={() => setSheetKey(null)}
        onChanged={() => void reload()}
        onAdvice={() => setAdvisor(true)}
        onPrepare={() => {
          if (sheetVolume) setFormatTarget({ key: sheetVolume.key, name: sheetVolume.name });
          setSheetKey(null);
        }}
      />
      <FormatWizard {...ctx} target={formatTarget} onClose={() => setFormatTarget(null)} onChanged={() => void reload()} />
      <FormatAdvisor {...ctx} open={advisor} onClose={() => setAdvisor(false)} />
    </div>
  );
}
