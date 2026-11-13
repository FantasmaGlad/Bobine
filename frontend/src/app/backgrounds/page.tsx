"use client";

import React, { useEffect, useRef, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { ARCHIVE_ACCEPT, VIDEO_ACCEPT, isArchiveName } from "@/lib/mediaFiles";
import { useUploadManager, PendingUploadSpec } from "@/lib/UploadManager";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import { useToast } from "@/lib/useToast";
import BackgroundCard from "@/components/backgrounds/BackgroundCard";
import BackgroundInspector from "@/components/backgrounds/BackgroundInspector";
import PendingBackgrounds from "@/components/backgrounds/PendingBackgrounds";
import type { BackgroundItem } from "@/components/backgrounds/types";

export default function BackgroundsPage() {
  const { t } = useAppSettings();

  const { state: cableState, sendCommand: sendCableCommand } = usePlaybackSocket(undefined, undefined, "cable");
  const { state: networkState, sendCommand: sendNetworkCommand } = usePlaybackSocket(undefined, undefined, "network");

  const [backgrounds, setBackgrounds] = useState<BackgroundItem[]>([]);
  const [defaultCoachBgId, setDefaultCoachBgId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const { toast, showToast } = useToast();

  const [inspectingBg, setInspectingBg] = useState<BackgroundItem | null>(null);

  const [pendingSpecs, setPendingSpecs] = useState<Array<PendingUploadSpec & { key: string }>>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addUploads, uploads } = useUploadManager();
  const seenDoneIds = useRef<Set<string>>(new Set());

  const [toDelete, setToDelete] = useState<BackgroundItem | null>(null);

  const fetchSettings = async () => {
    try {
      const res = await fetch(getApiUrl("/settings"), { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setDefaultCoachBgId(
          typeof data.default_coach_background_id === "number" ? data.default_coach_background_id : null
        );
      }
    } catch {
    }
  };

  const fetchBackgrounds = async () => {
    setLoading(true);
    try {
      const res = await fetch(getApiUrl("/backgrounds"), { cache: "no-store" });
      if (res.ok) {
        setBackgrounds(await res.json());
      } else {
        showToast(t("backgrounds.fetchError"), "error");
      }
    } catch {
      showToast(t("backgrounds.connectionError"), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBackgrounds();
    fetchSettings();
  }, []);

  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => (u.kind === "background" || u.kind === "background_zip") && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    fetchBackgrounds();
  }, [uploads]);

  const addFiles = (all: File[]) => {
    const archives = all.filter((f) => isArchiveName(f.name));
    if (archives.length > 0) addUploads(archives.map((file) => ({ kind: "background_zip" as const, file, title: file.name })));
    const files = all.filter((f) => !isArchiveName(f.name));
    if (files.length > 0) addPendingSpecs(files);
  };

  const addPendingSpecs = (files: File[]) => {
    const specs = files.map((file) => ({
      key: Math.random().toString(36).slice(2),
      kind: "background" as const,
      file,
      title: file.name.substring(0, file.name.lastIndexOf(".")) || file.name,
    }));
    setPendingSpecs((prev) => [...prev, ...specs]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) addFiles(Array.from(e.dataTransfer.files));
  };

  const updatePendingSpec = (key: string, patch: Partial<PendingUploadSpec>) => {
    setPendingSpecs((prev) => prev.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  };

  const removePendingSpec = (key: string) => {
    setPendingSpecs((prev) => prev.filter((s) => s.key !== key));
  };

  const submitPendingUploads = () => {
    if (pendingSpecs.length === 0) return;
    addUploads(pendingSpecs.map(({ file, title }) => ({ kind: "background" as const, file, title })));
    setPendingSpecs([]);
  };

  const handleToggleDefaultCoach = async (bgId: number) => {
    const newId = defaultCoachBgId === bgId ? null : bgId;
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ default_coach_background_id: newId }),
      });
      if (res.ok) {
        setDefaultCoachBgId(newId);
        showToast(
          newId !== null
            ? t("backgrounds.defaultSetToast")
            : t("backgrounds.defaultClearedToast"),
          "success"
        );
      } else {
        showToast(t("backgrounds.defaultErrorToast"), "error");
      }
    } catch {
      showToast(t("backgrounds.defaultErrorToast"), "error");
    }
  };

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
      const res = await fetch(getApiUrl(`/backgrounds/${toDelete.id}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("backgrounds.deletedToast"));
        setBackgrounds((prev) => prev.filter((b) => b.id !== toDelete.id));
        if (inspectingBg?.id === toDelete.id) setInspectingBg(null);
        if (defaultCoachBgId === toDelete.id) setDefaultCoachBgId(null);
      } else {
        showToast(t("backgrounds.deleteError"), "error");
      }
    } finally {
      setToDelete(null);
    }
  };

  const isCableBgActive = cableState.state === "background";
  const isNetworkBgActive = networkState.state === "background";

  return (
    <div
      className="library-container"
      onDragEnter={handleDrag}
      onDragOver={handleDrag}
      onDragLeave={handleDrag}
      onDrop={handleDrop}
    >
      {toast && (
        <div className={`toast ${toast.type}`}>
          <span>{toast.message}</span>
        </div>
      )}

      <div className="library-header-bar" style={{ marginBottom: "8px" }}>
        <div>
          <h1 style={{ fontFamily: "var(--font-title)", fontSize: "1.5rem", fontWeight: 900, margin: "0 0 4px" }}>
            {t("backgrounds.hubTitle")}
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0, maxWidth: "680px" }}>
            {t("backgrounds.hubSubtitle")}
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <input
            ref={fileInputRef}
            type="file"
            accept={`${VIDEO_ACCEPT},image/*,${ARCHIVE_ACCEPT}`}
            multiple
            style={{ display: "none" }}
            onChange={(e) => {
              if (e.target.files?.length) addFiles(Array.from(e.target.files));
              e.target.value = "";
            }}
          />
          <button
            type="button"
            className="btn btn-primary"
            style={{ height: "40px", padding: "0 16px", fontSize: "0.85rem" }}
            onClick={() => fileInputRef.current?.click()}
          >
            <Icon name="cloud_upload" size={18} />
            <span>Importer</span>
          </button>
        </div>
      </div>

      {(isCableBgActive || isNetworkBgActive) && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "20px" }}>
          {isCableBgActive && (
            <div
              className="interrupted-block"
              style={{ borderColor: "color-mix(in srgb, var(--accent-success) 40%, transparent)", margin: 0 }}
            >
              <div className="interrupted-text">
                <span className="interrupted-label" style={{ color: "var(--accent-success-text)", display: "flex", alignItems: "center", gap: "6px" }}>
                  <Icon name="cable" size={16} />
                  {t("backgrounds.onCable")} · {t("backgrounds.onScreenNow")}
                </span>
                <span className="interrupted-title">{cableState.current_background?.title}</span>
              </div>
              <button className="btn btn-secondary" onClick={() => sendCableCommand("stop")}>
                {t("backgrounds.stop")}
              </button>
            </div>
          )}
          {isNetworkBgActive && (
            <div
              className="interrupted-block"
              style={{ borderColor: "color-mix(in srgb, var(--accent-primary) 40%, transparent)", margin: 0 }}
            >
              <div className="interrupted-text">
                <span className="interrupted-label" style={{ color: "var(--accent-text)", display: "flex", alignItems: "center", gap: "6px" }}>
                  <Icon name="wifi" size={16} />
                  {t("backgrounds.onNetwork")} · {t("backgrounds.onScreenNow")}
                </span>
                <span className="interrupted-title">{networkState.current_background?.title}</span>
              </div>
              <button className="btn btn-secondary" onClick={() => sendNetworkCommand("stop")}>
                {t("backgrounds.stop")}
              </button>
            </div>
          )}
        </div>
      )}

      {(dragActive || pendingSpecs.length > 0) && (
        <PendingBackgrounds
          t={t}
          dragActive={dragActive}
          pendingSpecs={pendingSpecs}
          fileInputRef={fileInputRef}
          handleDrag={handleDrag}
          handleDrop={handleDrop}
          updatePendingSpec={updatePendingSpec}
          removePendingSpec={removePendingSpec}
          submitPendingUploads={submitPendingUploads}
          clearPendingSpecs={() => setPendingSpecs([])}
        />
      )}

      {loading ? (
        <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
          {t("backgrounds.loadingBackgrounds")}
        </div>
      ) : backgrounds.length === 0 ? (
        <div style={{ display: "flex", flex: 1, flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
          <p style={{ margin: 0, fontWeight: 600 }}>{t("backgrounds.noBackgroundsTitle")}</p>
          <p style={{ fontSize: "0.85rem", margin: "4px 0 0" }}>{t("backgrounds.noBackgroundsHint")}</p>
        </div>
      ) : (
        <div className="videos-grid">
          {backgrounds.map((bg) => (
            <BackgroundCard
              key={bg.id}
              bg={bg}
              isDefault={defaultCoachBgId === bg.id}
              isActiveCable={cableState.state === "background" && cableState.current_background?.id === bg.id}
              isActiveNetwork={networkState.state === "background" && networkState.current_background?.id === bg.id}
              onClick={() => setInspectingBg(bg)}
              onDelete={() => setToDelete(bg)}
            />
          ))}
        </div>
      )}

      {inspectingBg && (
        <BackgroundInspector
          t={t}
          bg={inspectingBg}
          isDefault={defaultCoachBgId === inspectingBg.id}
          onClose={() => setInspectingBg(null)}
          onToggleDefault={handleToggleDefaultCoach}
          onBroadcastCable={handleBroadcastCable}
          onBroadcastNetwork={handleBroadcastNetwork}
          onDelete={setToDelete}
        />
      )}

      {toDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>{t("backgrounds.deleteBackgroundTitle")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("backgrounds.deleteBackgroundConfirmBefore")}{" "}
              <strong style={{ color: "var(--text-main)" }}>{toDelete.title}</strong>{t("backgrounds.deleteBackgroundConfirmAfter")}
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setToDelete(null)}>
                {t("common.cancel")}
              </button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={confirmDelete}>
                {t("backgrounds.confirmDelete")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
