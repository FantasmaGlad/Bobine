"use client";

import React, { useRef, useState } from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import AnnouncementList from "@/components/radio-announcements/AnnouncementList";
import DeleteAnnouncementDialog from "@/components/radio-announcements/DeleteAnnouncementDialog";
import ImportCard from "@/components/radio-announcements/ImportCard";
import RulesPanel from "@/components/radio-announcements/RulesPanel";
import type { RuleTarget } from "@/components/radio-announcements/types";
import { useAnnouncementImport } from "@/components/radio-announcements/useAnnouncementImport";
import { useAnnouncements } from "@/components/radio-announcements/useAnnouncements";
import { usePlayNow } from "@/components/radio-announcements/usePlayNow";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useToast } from "@/lib/useToast";

export default function RadioAnnouncementsPage() {
  const { t } = useAppSettings();
  const { toast, showToast } = useToast();
  const list = useAnnouncements(t, showToast);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const io = useAnnouncementImport(fileInputRef, t, showToast, list.fetchAll);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const { playNowTarget, setPlayNowTarget, handlePlayNow } = usePlayNow(t, showToast);

  const targetOptions = [
    { value: "radio_network", label: t("radioAnnouncements.targetNetwork") },
    { value: "radio_cable", label: t("radioAnnouncements.targetCable") },
    { value: "both", label: t("radioAnnouncements.targetBoth") },
  ];

  return (
    <div className="ra-page" onDragEnter={io.handleDrag} onDragOver={io.handleDrag} onDragLeave={io.handleDrag} onDrop={io.handleDrop}>
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}

      <div className="ra-header" style={{ justifyContent: "flex-end" }}>
        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className="btn btn-secondary" onClick={() => io.setShowImportCard((v) => !v)} style={{ height: "44px" }}>
            <Icon name="cloud_upload" size={18} />
            <span>{io.showImportCard ? t("radioAnnouncements.closeImport") : t("radioAnnouncements.openImport")}</span>
          </button>
          <ResponsiveSelect
            className="form-control"
            style={{ height: "44px", width: "auto", minWidth: "190px" }}
            value={playNowTarget}
            onChange={(value) => setPlayNowTarget(value as RuleTarget)}
            title={t("radioAnnouncements.playNowTargetTitle")}
            options={targetOptions}
          />
          <button className="btn btn-primary ra-playnow" onClick={() => handlePlayNow()} disabled={list.announcements.filter((a) => a.enabled).length === 0}>
            <Icon name="play_arrow" size={18} filled /> {t("radioAnnouncements.playNow")}
          </button>
        </div>
      </div>

      <div className="ra-grid">
        <section className="ra-col">
          {(io.showImportCard || io.dragActive || Boolean(io.selectedFileName)) && <ImportCard io={io} fileInputRef={fileInputRef} />}
          <AnnouncementList
            announcements={list.announcements}
            loading={list.loading}
            onSave={list.saveDescription}
            onToggle={list.toggleEnabled}
            onPlay={handlePlayNow}
            onAskDelete={setConfirmDeleteId}
          />
        </section>
        <RulesPanel t={t} rules={list.rules} setRules={list.setRules} fetchAll={list.fetchAll} showToast={showToast} targetOptions={targetOptions} />
      </div>

      {confirmDeleteId !== null && (
        <DeleteAnnouncementDialog
          description={list.announcements.find((a) => a.id === confirmDeleteId)?.description || ""}
          onCancel={() => setConfirmDeleteId(null)}
          onConfirm={async () => {
            await list.remove(confirmDeleteId);
            setConfirmDeleteId(null);
          }}
        />
      )}
    </div>
  );
}
