"use client";

import React, { useRef, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useUploadManager } from "@/lib/UploadManager";
import { useToast } from "@/lib/useToast";
import ActiveBackgroundBanner from "@/components/backgrounds/ActiveBackgroundBanner";
import BackgroundGrid from "@/components/backgrounds/BackgroundGrid";
import BackgroundInspector from "@/components/backgrounds/BackgroundInspector";
import BackgroundsHeader from "@/components/backgrounds/BackgroundsHeader";
import DeleteBackgroundModal from "@/components/backgrounds/DeleteBackgroundModal";
import PendingBackgrounds from "@/components/backgrounds/PendingBackgrounds";
import type { BackgroundItem } from "@/components/backgrounds/types";
import { useBackgroundLibrary } from "@/components/backgrounds/useBackgroundLibrary";
import { usePendingBackgrounds } from "@/components/backgrounds/usePendingBackgrounds";

export default function BackgroundsPage() {
  const { t } = useAppSettings();
  const { state: cableState, sendCommand: sendCableCommand } = usePlaybackSocket(undefined, undefined, "cable");
  const { state: networkState, sendCommand: sendNetworkCommand } = usePlaybackSocket(undefined, undefined, "network");
  const { toast, showToast } = useToast();
  const [inspectingBg, setInspectingBg] = useState<BackgroundItem | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addUploads, uploads } = useUploadManager();
  const { pendingSpecs, clearPendingSpecs, dragActive, addFiles, handleDrag, handleDrop, updatePendingSpec, removePendingSpec, submitPendingUploads } = usePendingBackgrounds(addUploads);
  const [toDelete, setToDelete] = useState<BackgroundItem | null>(null);
  const { backgrounds, defaultCoachBgId, loading, handleToggleDefaultCoach, deleteBackground } = useBackgroundLibrary(t, showToast, uploads);

  const handleBroadcastCable = (bg: BackgroundItem) => {
    sendCableCommand("load_background", { background_id: bg.id });
    showToast(t("backgrounds.launchedCableToast", { title: bg.title }));
  };
  const handleBroadcastNetwork = (bg: BackgroundItem) => {
    sendNetworkCommand("load_background", { background_id: bg.id });
    showToast(t("backgrounds.launchedNetworkToast", { title: bg.title }));
  };
  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      if ((await deleteBackground(toDelete)) && inspectingBg?.id === toDelete.id) setInspectingBg(null);
    } finally {
      setToDelete(null);
    }
  };

  const isCableBgActive = cableState.state === "background";
  const isNetworkBgActive = networkState.state === "background";

  return (
    <div className="library-container" onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleDrop}>
      {toast && (
        <div className={`toast ${toast.type}`}>
          <span>{toast.message}</span>
        </div>
      )}
      <BackgroundsHeader t={t} fileInputRef={fileInputRef} addFiles={addFiles} />
      {(isCableBgActive || isNetworkBgActive) && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "20px" }}>
          {isCableBgActive && (
            <ActiveBackgroundBanner accent="var(--accent-success)" labelColor="var(--accent-success-text)" icon="cable"
              label={`${t("backgrounds.onCable")} · ${t("backgrounds.onScreenNow")}`} title={cableState.current_background?.title}
              stopLabel={t("backgrounds.stop")} onStop={() => sendCableCommand("stop")} />
          )}
          {isNetworkBgActive && (
            <ActiveBackgroundBanner accent="var(--accent-primary)" labelColor="var(--accent-text)" icon="wifi"
              label={`${t("backgrounds.onNetwork")} · ${t("backgrounds.onScreenNow")}`} title={networkState.current_background?.title}
              stopLabel={t("backgrounds.stop")} onStop={() => sendNetworkCommand("stop")} />
          )}
        </div>
      )}
      {(dragActive || pendingSpecs.length > 0) && (
        <PendingBackgrounds
          t={t} dragActive={dragActive} pendingSpecs={pendingSpecs} fileInputRef={fileInputRef}
          handleDrag={handleDrag} handleDrop={handleDrop} updatePendingSpec={updatePendingSpec}
          removePendingSpec={removePendingSpec} submitPendingUploads={submitPendingUploads} clearPendingSpecs={clearPendingSpecs}
        />
      )}
      <BackgroundGrid t={t} loading={loading} backgrounds={backgrounds} defaultCoachBgId={defaultCoachBgId}
        cableState={cableState} networkState={networkState} onInspect={setInspectingBg} onDelete={setToDelete} />
      {inspectingBg && (
        <BackgroundInspector
          t={t} bg={inspectingBg} isDefault={defaultCoachBgId === inspectingBg.id} onClose={() => setInspectingBg(null)}
          onToggleDefault={handleToggleDefaultCoach} onBroadcastCable={handleBroadcastCable}
          onBroadcastNetwork={handleBroadcastNetwork} onDelete={setToDelete}
        />
      )}
      {toDelete && <DeleteBackgroundModal t={t} target={toDelete} onCancel={() => setToDelete(null)} onConfirm={confirmDelete} />}
    </div>
  );
}
