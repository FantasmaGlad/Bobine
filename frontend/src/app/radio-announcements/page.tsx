"use client";

import React, { useRef, useState } from "react";
import Icon from "@/components/Icon";
import PageNav from "@/components/PageNav";
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
import { oneOf } from "@/lib/urlView";
import { useUrlView } from "@/lib/useUrlView";
import { useToast } from "@/lib/useToast";

const VIEWS = oneOf(["announcements", "rules"] as const, "announcements");

export default function RadioAnnouncementsPage() {
  const { t } = useAppSettings();
  const [view, setView] = useUrlView("vue", VIEWS);
  const { toast, showToast } = useToast();
  const list = useAnnouncements(t, showToast);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const io = useAnnouncementImport(fileInputRef, t, showToast, list.fetchAll);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const { playNowTarget, setPlayNowTarget, handlePlayNow } = usePlayNow(t, showToast);
  const announcements = view === "announcements";

  const targetOptions = [
    { value: "radio_network", label: t("radioAnnouncements.targetNetwork") },
    { value: "radio_cable", label: t("radioAnnouncements.targetCable") },
    { value: "both", label: t("radioAnnouncements.targetBoth") },
  ];

  const actions = (
    <div className="ra-actions">
      <button type="button" className="btn btn-secondary" onClick={() => { setView("announcements"); io.setShowImportCard((v) => !v); }}>
        <Icon name="cloud_upload" size={18} />
        <span>{io.showImportCard ? t("radioAnnouncements.closeImport") : t("radioAnnouncements.openImport")}</span>
      </button>
      <div className="ra-playnow-group">
        <ResponsiveSelect className="form-control" value={playNowTarget} onChange={(value) => setPlayNowTarget(value as RuleTarget)}
          title={t("radioAnnouncements.playNowTargetTitle")} options={targetOptions} />
        <button type="button" className="btn btn-primary" onClick={() => handlePlayNow()} disabled={list.announcements.filter((a) => a.enabled).length === 0}>
          <Icon name="play_arrow" size={18} filled /> {t("radioAnnouncements.playNow")}
        </button>
      </div>
    </div>
  );

  return (
    <div className="ra-page" onDragEnter={io.handleDrag} onDragOver={io.handleDrag} onDragLeave={io.handleDrag} onDrop={(e) => { setView("announcements"); io.handleDrop(e); }}>
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      <PageNav
        tabs={[
          { id: "announcements", icon: "campaign", label: t("radioAnnouncements.tabAnnouncements"), count: list.announcements.length },
          { id: "rules", icon: "schedule", label: t("radioAnnouncements.tabRules"), count: list.rules.length },
        ]}
        value={view}
        onChange={(id) => setView(VIEWS(id))}
        ariaLabel={t("radioAnnouncements.sectionsLabel")}
        actions={actions}
      />
      {announcements ? (
        <>
          {(io.showImportCard || io.dragActive || Boolean(io.selectedFileName)) && <ImportCard io={io} fileInputRef={fileInputRef} />}
          <AnnouncementList announcements={list.announcements} loading={list.loading} onSave={list.saveDescription}
            onToggle={list.toggleEnabled} onPlay={handlePlayNow} onAskDelete={setConfirmDeleteId} />
        </>
      ) : (
        <RulesPanel t={t} rules={list.rules} setRules={list.setRules} fetchAll={list.fetchAll} showToast={showToast} targetOptions={targetOptions} />
      )}
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
