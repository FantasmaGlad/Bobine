"use client";

import React, { useEffect, useRef, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useUploadManager, PendingUploadSpec } from "@/lib/UploadManager";
import Icon from "@/components/Icon";

interface BackgroundItem {
  id: number;
  file_path: string;
  title: string;
  duration_seconds: number | null;
  thumbnail_path: string | null;
  is_image: boolean;
}

interface ToastState {
  message: string;
  type: "success" | "error" | "warning";
}

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

function BackgroundCard({
  bg,
  isDefault,
  isActiveCable,
  isActiveNetwork,
  onClick,
  onDelete,
}: {
  bg: BackgroundItem;
  isDefault: boolean;
  isActiveCable: boolean;
  isActiveNetwork: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const { t } = useAppSettings();
  const [hovering, setHovering] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (hovering && !bg.is_image) {
      video.currentTime = 0;
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  }, [hovering, bg.is_image]);

  const thumbSrc = bg.thumbnail_path
    ? getApiUrl(`/thumbnails/${bg.thumbnail_path.split("/").pop()}`)
    : null;

  return (
    <div
      className={`video-card olc-press ${isActiveCable || isActiveNetwork ? "program-rpm" : ""}`}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onClick={onClick}
      style={{ cursor: "pointer", position: "relative" }}
    >
      <div className="thumbnail-wrapper" style={{ position: "relative", aspectRatio: "16/9", overflow: "hidden", borderRadius: "10px" }}>
        {hovering && !bg.is_image ? (
          <video
            ref={videoRef}
            className="card-thumbnail"
            src={getApiUrl(`/backgrounds/${bg.id}/stream`)}
            muted
            loop
            playsInline
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : thumbSrc ? (
          <img
            src={thumbSrc}
            alt={bg.title}
            className="card-thumbnail"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "var(--bg-surface-elevated)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name={bg.is_image ? "image" : "gradient"} size={32} style={{ opacity: 0.3 }} />
          </div>
        )}

        {/* Badges en superposition */}
        <div style={{ position: "absolute", top: 8, left: 8, display: "flex", flexDirection: "column", gap: "6px", zIndex: 3 }}>
          {isDefault && (
            <span
              style={{
                background: "var(--accent-primary)",
                color: "var(--accent-primary-fg)",
                padding: "3px 8px",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
              }}
            >
              <Icon name="bookmark" size={13} filled />
              {t("backgrounds.defaultBadge")}
            </span>
          )}
        </div>

        <div style={{ position: "absolute", top: 8, right: 8, display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-end", zIndex: 3 }}>
          {isActiveCable && (
            <span
              style={{
                background: "var(--accent-success)",
                color: "#ffffff",
                padding: "3px 8px",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
              }}
            >
              <Icon name="cable" size={13} />
              {t("backgrounds.onCable")}
            </span>
          )}
          {isActiveNetwork && (
            <span
              style={{
                background: "var(--accent-primary)",
                color: "var(--accent-primary-fg)",
                padding: "3px 8px",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
              }}
            >
              <Icon name="wifi" size={13} />
              {t("backgrounds.onNetwork")}
            </span>
          )}
        </div>

        <span
          className="card-duration"
          style={{
            position: "absolute",
            bottom: 8,
            right: 8,
            background: "rgba(0, 0, 0, 0.75)",
            color: "#ffffff",
            padding: "2px 6px",
            borderRadius: "4px",
            fontSize: "0.72rem",
            fontWeight: 600,
          }}
        >
          {bg.duration_seconds ? `${Math.round(bg.duration_seconds)}s` : t("backgrounds.infiniteLoop")}
        </span>
      </div>

      <div className="card-content" style={{ padding: "12px 6px 6px" }}>
        <h4 className="card-title" title={bg.title} style={{ fontSize: "0.95rem", fontWeight: 700, margin: "0 0 6px" }}>
          {bg.title}
        </h4>
        <div className="card-meta-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="release-badge" style={{ fontSize: "0.75rem" }}>
            {bg.is_image ? "Image" : "Vidéo"}
          </span>
          <button
            type="button"
            className="btn btn-danger"
            style={{ height: "30px", padding: "0 8px", fontSize: "0.75rem", display: "inline-flex", alignItems: "center", gap: "4px" }}
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            title={t("common.delete")}
          >
            <Icon name="delete" size={15} />
            {t("common.delete")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function BackgroundsPage() {
  const { t } = useAppSettings();

  // Écoute des deux sorties (câblée et réseau) pour refléter l'état réel de diffusion
  const { state: cableState, sendCommand: sendCableCommand } = usePlaybackSocket(undefined, undefined, "cable");
  const { state: networkState, sendCommand: sendNetworkCommand } = usePlaybackSocket(undefined, undefined, "network");

  const [backgrounds, setBackgrounds] = useState<BackgroundItem[]>([]);
  const [defaultCoachBgId, setDefaultCoachBgId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  // Modale d'aperçu / inspection
  const [inspectingBg, setInspectingBg] = useState<BackgroundItem | null>(null);

  // Uploads
  const [pendingSpecs, setPendingSpecs] = useState<Array<PendingUploadSpec & { key: string }>>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addUploads, uploads } = useUploadManager();
  const seenDoneIds = useRef<Set<string>>(new Set());

  // Suppression
  const [toDelete, setToDelete] = useState<BackgroundItem | null>(null);

  const showToast = (message: string, type: ToastState["type"] = "success") => setToast({ message, type });

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

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
      // Ignorer silencieusement
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

  // Rafraîchit la liste dès qu'un import se termine
  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => u.kind === "background" && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    fetchBackgrounds();
  }, [uploads]);

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
    if (e.dataTransfer.files?.length) addPendingSpecs(Array.from(e.dataTransfer.files));
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
    <div className="library-container">
      {toast && (
        <div className={`toast ${toast.type}`}>
          <span>{toast.message}</span>
        </div>
      )}

      {/* En-tête de section Hub d'Ambiances */}
      <div style={{ marginBottom: "20px" }}>
        <h1 style={{ fontFamily: "var(--font-title)", fontSize: "1.6rem", fontWeight: 900, margin: "0 0 6px" }}>
          {t("backgrounds.hubTitle")}
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", margin: 0, maxWidth: "680px" }}>
          {t("backgrounds.hubSubtitle")}
        </p>
      </div>

      {/* Bandeaux de statut si une ambiance est active en direct */}
      {(isCableBgActive || isNetworkBgActive) && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "20px" }}>
          {isCableBgActive && (
            <div
              className="interrupted-block"
              style={{ borderColor: "color-mix(in srgb, var(--accent-success) 40%, transparent)", margin: 0 }}
            >
              <div className="interrupted-text">
                <span className="interrupted-label" style={{ color: "var(--accent-success)", display: "flex", alignItems: "center", gap: "6px" }}>
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
                <span className="interrupted-label" style={{ color: "var(--accent-primary)", display: "flex", alignItems: "center", gap: "6px" }}>
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

      {/* Zone de téléversement Drag & Drop */}
      <div
        className={`upload-zone ${dragActive ? "drag-active" : ""}`}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => {
          if (pendingSpecs.length === 0 && fileInputRef.current) fileInputRef.current.click();
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*,image/*"
          multiple
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files?.length) addPendingSpecs(Array.from(e.target.files));
            e.target.value = "";
          }}
        />
        {pendingSpecs.length === 0 ? (
          <>
            <Icon name="cloud_upload" size={48} className="upload-icon" />
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: "8px 0 4px" }}>
              {t("backgrounds.dropHint")}
            </h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
              {t("backgrounds.formatsHint")}
            </p>
          </>
        ) : (
          <div onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: "560px", textAlign: "left" }}>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "12px", color: "var(--accent-primary)", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px" }}>
              {pendingSpecs.length} fichier{pendingSpecs.length > 1 ? "s" : ""} sélectionné{pendingSpecs.length > 1 ? "s" : ""}
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "320px", overflowY: "auto", paddingRight: "4px" }}>
              {pendingSpecs.map((spec) => (
                <div key={spec.key} style={{ background: "var(--bg-surface-hover)", borderRadius: "8px", padding: "10px 12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={spec.file?.name}>
                      {spec.file?.name} ({((spec.file?.size ?? 0) / (1024 * 1024)).toFixed(1)} Mo)
                    </span>
                    <button onClick={() => removePendingSpec(spec.key)} className="olc-press" style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", flexShrink: 0, display: "flex" }}>
                      <Icon name="close" size={16} />
                    </button>
                  </div>
                  <input
                    type="text"
                    className="form-control"
                    placeholder={t("backgrounds.nameLabel")}
                    value={spec.title}
                    onChange={(e) => updatePendingSpec(spec.key, { title: e.target.value })}
                    style={{ padding: "6px 10px", fontSize: "0.85rem" }}
                  />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: "12px", marginTop: "14px" }}>
              <button type="button" className="btn btn-primary" onClick={submitPendingUploads} style={{ flex: 1, height: "44px" }}>
                {t("backgrounds.startImport")} ({pendingSpecs.length})
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setPendingSpecs([])} style={{ height: "44px" }}>
                {t("common.cancel")}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => fileInputRef.current?.click()} style={{ height: "44px", whiteSpace: "nowrap" }}>
                + Ajouter
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Grille des cartes d'ambiance */}
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

      {/* Modale d'inspection et de prévisualisation grand format */}
      {inspectingBg && (
        <div className="modal-overlay" onClick={() => setInspectingBg(null)}>
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "640px", width: "100%", padding: "24px" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Icon name={inspectingBg.is_image ? "image" : "videocam"} size={22} color="var(--accent-primary)" />
                <h3 style={{ fontSize: "1.2rem", fontWeight: 800, margin: 0 }}>
                  {inspectingBg.title}
                </h3>
              </div>
              <button
                className="coach-icon-btn olc-press"
                style={{ width: "36px", height: "36px", fontSize: "0.9rem" }}
                onClick={() => setInspectingBg(null)}
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            {/* Lecteur grand format */}
            <div style={{ position: "relative", width: "100%", aspectRatio: "16/9", borderRadius: "10px", overflow: "hidden", background: "#000", marginBottom: "16px" }}>
              {inspectingBg.is_image ? (
                <img
                  src={getApiUrl(`/backgrounds/${inspectingBg.id}/stream`)}
                  alt={inspectingBg.title}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <video
                  src={getApiUrl(`/backgrounds/${inspectingBg.id}/stream`)}
                  autoPlay
                  loop
                  muted
                  playsInline
                  controls
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              )}
            </div>

            {/* Métadonnées & Statut */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: "10px",
                padding: "12px",
                background: "var(--bg-surface-elevated)",
                borderRadius: "8px",
                marginBottom: "20px",
                fontSize: "0.85rem",
              }}
            >
              <div>
                <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.75rem" }}>{t("backgrounds.formatLabel")}</span>
                <strong style={{ color: "var(--text-main)" }}>{inspectingBg.is_image ? "Image fixe" : "Boucle vidéo"}</strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.75rem" }}>{t("backgrounds.durationLabel")}</span>
                <strong style={{ color: "var(--text-main)" }}>
                  {inspectingBg.duration_seconds ? `${Math.round(inspectingBg.duration_seconds)}s` : t("backgrounds.infiniteLoop")}
                </strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.75rem" }}>Mode Coach</span>
                <strong style={{ color: defaultCoachBgId === inspectingBg.id ? "var(--accent-primary)" : "var(--text-muted)" }}>
                  {defaultCoachBgId === inspectingBg.id ? "Par défaut" : "Optionnel"}
                </strong>
              </div>
            </div>

            {/* Actions principales */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  type="button"
                  className={`btn ${defaultCoachBgId === inspectingBg.id ? "btn-secondary" : "btn-primary"}`}
                  style={{ flex: 1, height: "44px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                  onClick={() => handleToggleDefaultCoach(inspectingBg.id)}
                >
                  <Icon name={defaultCoachBgId === inspectingBg.id ? "bookmark_remove" : "bookmark_add"} size={18} />
                  {defaultCoachBgId === inspectingBg.id ? "Retirer fond par défaut Coach" : t("backgrounds.setAsDefaultCoach")}
                </button>
              </div>

              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ flex: 1, minWidth: "200px", height: "44px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                  onClick={() => handleBroadcastCable(inspectingBg)}
                >
                  <Icon name="cable" size={18} color="var(--accent-success)" />
                  {t("backgrounds.broadcastCable")}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ flex: 1, minWidth: "200px", height: "44px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                  onClick={() => handleBroadcastNetwork(inspectingBg)}
                >
                  <Icon name="wifi" size={18} color="var(--accent-primary)" />
                  {t("backgrounds.broadcastNetwork")}
                </button>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ height: "38px", display: "inline-flex", alignItems: "center", gap: "6px" }}
                  onClick={() => {
                    setToDelete(inspectingBg);
                  }}
                >
                  <Icon name="delete" size={16} />
                  {t("common.delete")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation de suppression */}
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
