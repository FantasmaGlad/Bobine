"use client";

import React, { useEffect, useState, useRef } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { videoStreamUrl } from "@/lib/clientCodecSupport";
import WebRenditionPanel from "@/components/WebRenditionPanel";
import { useUploadManager, PendingUploadSpec } from "@/lib/UploadManager";
import { VIDEO_ACCEPT, SUBTITLE_ACCEPT, partitionVideoFiles } from "@/lib/mediaFiles";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { parseMediaName } from "@/lib/parseMediaName";
import Icon from "@/components/Icon";
import VideoPlaylistManager from "@/components/VideoPlaylistManager";
import {
  getResolutionBadge,
  getAudioQualityBadge,
  formatFps,
  formatBitrate,
} from "@/lib/videoBadges";
import { formatCleanDescription } from "@/lib/formatDescription";

interface VideoSubtitleItem {
  id: number;
  video_id: number;
  language_code: string;
  language_label: string;
  format: string;
  vtt_url: string;
}

interface Video {
  id: number;
  file_path: string;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  codec: string | null;
  thumbnail_path: string | null;
  source: string;
  description?: string | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
  fps?: number | null;
  bitrate_kbps?: number | null;
}

interface ToastState {
  message: string;
  type: "success" | "error" | "warning";
}

export default function LibraryPage() {
  const { t } = useAppSettings();
  // Bascule Médiathèque/Playlists : la création de playlist vidéo vit désormais ici plutôt
  // que sur une page /playlists séparée.
  const [mode, setMode] = useState<"media" | "playlists">("media");
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters & Search states
  const [search, setSearch] = useState<string>("");
  const [programFilter, setProgramFilter] = useState<string>("");
  const [releaseFilter, setReleaseFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("imported_at");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  // Selected video for details drawer
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);

  // Drawer Form fields. `drawerProgram` est un libellé LIBRE (plus de presets
  // RPM/Sprint/The Trip codés en dur) : saisie texte + suggestions (datalist)
  // des catégories déjà utilisées.
  const [drawerTitle, setDrawerTitle] = useState<string>("");
  const [drawerProgram, setDrawerProgram] = useState<string>("");
  const [drawerRelease, setDrawerRelease] = useState<string>("");
  const [drawerDescription, setDrawerDescription] = useState<string>("");
  const [isSavingDrawer, setIsSavingDrawer] = useState<boolean>(false);

  // Sous-titres pour le cours ouvert en Studio
  const [studioSubtitles, setStudioSubtitles] = useState<VideoSubtitleItem[]>([]);
  const [isLoadingSubtitles, setIsLoadingSubtitles] = useState<boolean>(false);
  const subtitleInputRef = useRef<HTMLInputElement>(null);

  // Catégories (programmes) réellement présentes dans la bibliothèque, pour
  // alimenter les suggestions de saisie, le filtre et le regroupement — plus
  // aucune liste figée.
  const [programs, setPrograms] = useState<string[]>([]);

  // Drag-and-drop zone
  const [dragActive, setDragActive] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const thumbnailInputRef = useRef<HTMLInputElement>(null);

  // Mini-formulaires pour préparer les métadonnées avant l'upload.
  // Chaque entrée correspond à un fichier sélectionné mais pas encore envoyé.
  const [pendingSpecs, setPendingSpecs] = useState<Array<PendingUploadSpec & { key: string }>>([]);

  // Delete modal confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [videoToDelete, setVideoToDelete] = useState<Video | null>(null);
  const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState<boolean>(false);

  // Sélection multiple
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [playlists, setPlaylists] = useState<{ id: number; name: string }[]>([]);
  const [showAddToPlaylist, setShowAddToPlaylist] = useState<boolean>(false);
  const [bulkTargetPlaylistId, setBulkTargetPlaylistId] = useState<string>("");

  // Toast state
  const [toast, setToast] = useState<ToastState | null>(null);

  // API URL Helper
  const getApiUrl = (path: string) => {
    if (typeof window !== "undefined") {
      if (window.location.port === "3000") {
        return `http://localhost:8001/api${path}`;
      }
    }
    return `/api${path}`;
  };

  // Upload Manager global
  const { addUploads, uploads } = useUploadManager();
  // Écoute passive uniquement (aucune commande envoyée depuis cette page) :
  // réagit à `library_change` — un import/modification/suppression fait ailleurs
  // (autre onglet, dossier surveillé) se reflète ici sans action manuelle.
  const { libraryVersion } = usePlaybackSocket();
  // `seenDoneIds` évite de
  // redéclencher un fetch à chaque tick de polling tant qu'aucune tâche
  // vidéo n'a nouvellement terminé (effet déclaré plus bas, après
  // `fetchVideos`).
  const seenDoneIds = useRef<Set<string>>(new Set());

  // Show toast helper
  const showToast = (message: string, type: "success" | "error" | "warning" = "success") => {
    setToast({ message, type });
  };

  // Auto-hide toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        setToast(null);
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Load videos
  const fetchVideos = async () => {
    await Promise.resolve();
    setLoading(true);
    try {
      const queryParams = new URLSearchParams();
      if (search) queryParams.append("search", search);
      if (programFilter) queryParams.append("program", programFilter);
      if (releaseFilter) queryParams.append("release", releaseFilter);
      queryParams.append("sort_by", sortBy);
      queryParams.append("order", "desc");

      const res = await fetch(getApiUrl(`/videos?${queryParams.toString()}`), {
        cache: "no-store",
      });
      if (res.ok) {
        const data = await res.json();
        setVideos(data);
      } else {
        showToast(t("library.fetchError"), "error");
      }
    } catch {
      showToast(t("library.connectionError"), "error");
    } finally {
      setLoading(false);
    }
  };

  // Rafraîchit la bibliothèque dès qu'un import vidéo se termine : les imports sont désormais
  // traités en arrière-plan (réponse HTTP 202 immédiate), sans ce suivi la
  // nouvelle vidéo n'apparaissait qu'après une action manuelle (changement
  // de filtre/tri).
  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => u.kind === "video" && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    fetchVideos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploads]);

  // Fetch videos on filter/search change
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchVideos();
  }, [search, programFilter, releaseFilter, sortBy]);


  useEffect(() => {
    fetch(getApiUrl("/playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setPlaylists)
      .catch(() => setPlaylists([]));
  }, []);

  const fetchPrograms = () => {
    fetch(getApiUrl("/videos/programs"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: string[]) => setPrograms(Array.isArray(data) ? data : []))
      .catch(() => {});
  };
  useEffect(fetchPrograms, []);

  // Recharge sur `library_change` venu d'ailleurs (autre onglet, dossier
  // surveillé) — `libraryVersion === 0` (valeur initiale, avant tout
  // évènement reçu) est ignoré : l'effet ci-dessus s'en charge déjà au
  // montage, inutile de refetcher une seconde fois pour rien.
  useEffect(() => {
    if (libraryVersion === 0) return;
    fetchVideos();
    fetchPrograms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [libraryVersion]);

  // Liste de suggestions = catégories du serveur ∪ celles des vidéos déjà
  // chargées (pour qu'une catégorie tout juste créée apparaisse sans attendre
  // un rechargement), triée sans casse.
  const availablePrograms = React.useMemo(() => {
    const set = new Set<string>(programs);
    for (const v of videos) if (v.program) set.add(v.program);
    return Array.from(set).sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
  }, [programs, videos]);

  const toggleSelected = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Sélection groupée : cases « tout sélectionner » (par groupe de programme en vue
  // grille, globale en vue liste) + sélection par plage au Maj-clic en liste.
  const setManySelected = (ids: number[], select: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (select) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  };
  const allSelected = (ids: number[]) => ids.length > 0 && ids.every((id) => selectedIds.has(id));

  // Dernière ligne cochée en vue liste, pour la sélection par plage (Maj-clic).
  const lastListIndexRef = useRef<number | null>(null);
  const handleRowCheckboxClick = (e: React.MouseEvent, index: number, id: number) => {
    if (e.shiftKey && lastListIndexRef.current !== null && lastListIndexRef.current !== index) {
      const [a, b] = [lastListIndexRef.current, index].sort((x, y) => x - y);
      const select = !selectedIds.has(id);
      setManySelected(videos.slice(a, b + 1).map((v) => v.id), select);
    } else {
      toggleSelected(id);
    }
    lastListIndexRef.current = index;
  };

  const clearSelection = () => setSelectedIds(new Set());

  const confirmBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(ids.map((id) => fetch(getApiUrl(`/videos/${id}`), { method: "DELETE" })));
    const failed = results.filter((r) => r.status === "rejected").length;
    showToast(
      failed > 0
        ? t("library.bulkDeletedPartial", { ok: ids.length - failed, total: ids.length })
        : t("library.bulkDeletedAll", { count: ids.length }),
      failed > 0 ? "warning" : "success"
    );
    setBulkDeleteConfirm(false);
    clearSelection();
    fetchVideos();
  };

  const confirmBulkAddToPlaylist = async () => {
    if (!bulkTargetPlaylistId) return;
    try {
      const res = await fetch(getApiUrl(`/playlists/${bulkTargetPlaylistId}`), { cache: "no-store" });
      if (!res.ok) throw new Error();
      const playlist = await res.json();
      const existingIds: number[] = playlist.items.map((i: { video: { id: number } }) => i.video.id);
      const newItems = [
        ...playlist.items.map((i: { video: { id: number } }, idx: number) => ({ video_id: i.video.id, position: idx })),
        ...Array.from(selectedIds)
          .filter((id) => !existingIds.includes(id))
          .map((id, idx) => ({ video_id: id, position: playlist.items.length + idx })),
      ];
      const putRes = await fetch(getApiUrl(`/playlists/${bulkTargetPlaylistId}`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: playlist.name, items: newItems }),
      });
      if (putRes.ok) {
        showToast(t("library.addedToPlaylist", { count: selectedIds.size, name: playlist.name }));
        setShowAddToPlaylist(false);
        setBulkTargetPlaylistId("");
        clearSelection();
      } else {
        showToast(t("library.addToPlaylistError"), "error");
      }
    } catch {
      showToast(t("library.addToPlaylistError"), "error");
    }
  };

  // Handle video card/row click -> Open Course Studio
  const handleSelectVideo = (video: Video) => {
    setSelectedVideo(video);
    setDrawerTitle(video.title);
    // Catégorie = libellé libre (plus de presets figés).
    setDrawerProgram(video.program || "");
    setDrawerRelease(video.release || "");
    setDrawerDescription(video.description || "");
    fetchSubtitles(video.id);
  };

  const fetchSubtitles = async (videoId: number) => {
    setIsLoadingSubtitles(true);
    try {
      const res = await fetch(getApiUrl(`/videos/${videoId}/subtitles`));
      if (res.ok) {
        const data = await res.json();
        setStudioSubtitles(Array.isArray(data) ? data : []);
      }
    } catch {
      // ignorer
    } finally {
      setIsLoadingSubtitles(false);
    }
  };

  const handleUploadSubtitle = async (file: File) => {
    if (!selectedVideo) return;
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(getApiUrl(`/videos/${selectedVideo.id}/subtitles`), {
        method: "POST",
        body,
      });
      if (res.ok) {
        showToast("Sous-titre ajouté avec succès", "success");
        fetchSubtitles(selectedVideo.id);
      } else {
        const errData = await res.json().catch(() => ({}));
        showToast(errData.detail || "Erreur d'import du sous-titre", "error");
      }
    } catch {
      showToast("Erreur de connexion", "error");
    }
  };

  const handleDeleteSubtitle = async (subId: number) => {
    if (!selectedVideo) return;
    try {
      const res = await fetch(getApiUrl(`/videos/${selectedVideo.id}/subtitles/${subId}`), {
        method: "DELETE",
      });
      if (res.ok) {
        showToast("Sous-titre supprimé", "success");
        setStudioSubtitles((prev) => prev.filter((s) => s.id !== subId));
      } else {
        showToast("Erreur lors de la suppression", "error");
      }
    } catch {
      showToast("Erreur de connexion", "error");
    }
  };

  // Close details drawer
  const handleCloseDrawer = () => {
    setSelectedVideo(null);
    setStudioSubtitles([]);
  };

  // Save Video Metadata from Drawer
  const handleSaveMetadata = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVideo) return;

    setIsSavingDrawer(true);
    const finalProgram = drawerProgram.trim();

    try {
      const res = await fetch(getApiUrl(`/videos/${selectedVideo.id}`), {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: drawerTitle,
          program: finalProgram || null,
          release: drawerRelease || null,
          description: formatCleanDescription(drawerDescription) || null,
        }),
      });

      if (res.ok) {
        const updatedVideo = await res.json();
        showToast(t("library.metadataSaved"));

        // Update video list in place
        setVideos((prev) =>
          prev.map((v) => (v.id === updatedVideo.id ? updatedVideo : v))
        );
        setSelectedVideo(updatedVideo);
        fetchPrograms(); // une nouvelle catégorie saisie doit alimenter les suggestions
      } else {
        const errData = await res.json();
        showToast(t("library.saveErrorDetail", { detail: errData.detail || t("library.saveErrorFallback") }), "error");
      }
    } catch {
      showToast(t("library.saveConnectionError"), "error");
    } finally {
      setIsSavingDrawer(false);
    }
  };

  // Normalize Video (remux / recode audio if needed)
  const handleNormalize = async () => {
    if (!selectedVideo) return;
    try {
      const res = await fetch(getApiUrl(`/videos/${selectedVideo.id}/normalize`), {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        showToast(data.message, "success");
      } else {
        const errData = await res.json();
        showToast(errData.detail || t("library.normalizeError"), "error");
      }
    } catch {
      showToast(t("library.normalizeNetworkError"), "error");
    }
  };

  // Miniature manuelle. Même mécanique que
  // handleSaveMetadata ci-dessus (met à jour la liste + le tiroir en place).
  const [isUploadingThumbnail, setIsUploadingThumbnail] = useState(false);
  const handleUploadThumbnail = async (file: File) => {
    if (!selectedVideo) return;
    setIsUploadingThumbnail(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(getApiUrl(`/videos/${selectedVideo.id}/thumbnail`), {
        method: "PUT",
        body,
      });
      if (res.ok) {
        const updatedVideo = await res.json();
        showToast(t("library.thumbnailSaved"));
        setVideos((prev) => prev.map((v) => (v.id === updatedVideo.id ? updatedVideo : v)));
        setSelectedVideo(updatedVideo);
      } else {
        const errData = await res.json();
        showToast(t("library.saveErrorDetail", { detail: errData.detail || t("library.saveErrorFallback") }), "error");
      }
    } catch {
      showToast(t("library.saveConnectionError"), "error");
    } finally {
      setIsUploadingThumbnail(false);
    }
  };

  // Trigger video deletion confirmation
  const triggerDelete = (video: Video) => {
    setVideoToDelete(video);
    setShowDeleteConfirm(true);
  };

  // Confirm and execute deletion
  const confirmDelete = async () => {
    if (!videoToDelete) return;
    try {
      const res = await fetch(getApiUrl(`/videos/${videoToDelete.id}`), {
        method: "DELETE",
      });
      if (res.ok) {
        showToast(t("library.deletedSuccess"));
        setVideos((prev) => prev.filter((v) => v.id !== videoToDelete.id));
        if (selectedVideo?.id === videoToDelete.id) {
          setSelectedVideo(null);
        }
      } else {
        showToast(t("library.deleteError"), "error");
      }
    } catch {
      showToast(t("library.deleteGenericError"), "error");
    } finally {
      setShowDeleteConfirm(false);
      setVideoToDelete(null);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    acceptDroppedOrSelected(Array.from(e.dataTransfer.files));
  };

  /** Ajoute les fichiers vidéo et sous-titres reconnus (type MIME OU extension, cf.
   *  lib/mediaFiles.ts) et prévient explicitement pour les autres. */
  const acceptDroppedOrSelected = (files: File[]) => {
    const { accepted, subtitles, rejected } = partitionVideoFiles(files);
    if (accepted.length > 0) {
      addPendingSpecs(accepted, subtitles);
    } else if (subtitles.length > 0) {
      // Sous-titres déposés seuls : rattachés au premier cours en attente
      setPendingSpecs((prev) => {
        if (prev.length === 0) {
          showToast("Veuillez d'abord sélectionner une vidéo pour lui associer ce sous-titre", "warning");
          return prev;
        }
        const first = prev[0];
        const updatedSubs = [...(first.subtitles ?? []), ...subtitles];
        return [{ ...first, subtitles: updatedSubs }, ...prev.slice(1)];
      });
      showToast(`${subtitles.length} sous-titre(s) rattaché(s)`, "success");
    }
    if (rejected.length > 0) {
      const names = rejected.slice(0, 3).map((f) => f.name).join(", ") + (rejected.length > 3 ? "…" : "");
      showToast(t("library.unsupportedFiles", { count: rejected.length, names }), "warning");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) acceptDroppedOrSelected(files);
    // Réinitialiser l'input pour permettre de re-sélectionner les mêmes fichiers.
    e.target.value = "";
  };

  /** Crée les PendingSpec avec métadonnées pré-remplies par heuristique et
   *  rattachement automatique des sous-titres (.srt/.vtt) correspondants. */
  const addPendingSpecs = (files: File[], droppedSubtitles: File[] = []) => {
    const known = availablePrograms;
    const specs = files.map((file) => {
      const { title, program, release } = parseMediaName(file.name, known);
      const baseStem = file.name.substring(0, file.name.lastIndexOf(".")).toLowerCase();
      const matchedSubs = droppedSubtitles.filter((sub) => {
        const subLower = sub.name.toLowerCase();
        return subLower.startsWith(baseStem) || files.length === 1;
      });
      return {
        key: Math.random().toString(36).slice(2),
        kind: "video" as const,
        file,
        title,
        program,
        release,
        description: "",
        subtitles: matchedSubs,
      };
    });
    setPendingSpecs((prev) => [...prev, ...specs]);
  };

  const updatePendingSpec = (key: string, patch: Partial<PendingUploadSpec>) => {
    setPendingSpecs((prev) => prev.map((s) => s.key === key ? { ...s, ...patch } : s));
  };

  const removePendingSpec = (key: string) => {
    setPendingSpecs((prev) => prev.filter((s) => s.key !== key));
  };

  const submitPendingUploads = () => {
    if (pendingSpecs.length === 0) return;
    addUploads(
      pendingSpecs.map(({ file, title, program, release, description, subtitles }) => ({
        kind: "video" as const,
        file,
        title,
        program,
        release,
        description: formatCleanDescription(description) || undefined,
        subtitles,
      }))
    );
    setPendingSpecs([]);
  };

  // Helper formats
  const formatDuration = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return "--:--";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Catégories libres : plus de couleur par programme (RPM/Sprint/… mappaient
  // déjà tous vers l'accent du thème en CSS). Une seule classe générique suffit.
  const getProgramClass = (_program: string | null) => "program-autre";
  const getProgramBadgeClass = (_program: string | null) => "autre";

  const getThumbnailSrc = (video: Video) => {
    if (!video.thumbnail_path) return null;
    const filename = video.thumbnail_path.split("/").pop();
    if (!filename) return null;
    return getApiUrl(`/thumbnails/${filename}`);
  };

  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  return (
    <div
      className={`library-container ${mode === "playlists" ? "playlists-mode" : ""}`}
      onDragEnter={mode === "media" ? handleDrag : undefined}
      onDragOver={mode === "media" ? handleDrag : undefined}
      onDragLeave={mode === "media" ? handleDrag : undefined}
      onDrop={mode === "media" ? handleDrop : undefined}
    >
      {/* Bascule Médiathèque/Playlists : mêmes boutons que le bascule
          grille/liste ci-dessous (.view-toggle), pour rester dans le même
          langage visuel plutôt qu'introduire un nouveau composant d'onglet. */}
      <div className="library-header-bar">
        <div className="view-toggle">
          <button
            className={`view-btn olc-press ${mode === "media" ? "active" : ""}`}
            onClick={() => setMode("media")}
          >
            <Icon name="video_library" size={16} /> {t("library.mediaTab")}
          </button>
          <button
            className={`view-btn olc-press ${mode === "playlists" ? "active" : ""}`}
            onClick={() => setMode("playlists")}
          >
            <Icon name="playlist_play" size={16} /> {t("library.playlistsTab")}
          </button>
        </div>

        {mode === "media" && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <input
              ref={fileInputRef}
              type="file"
              accept={VIDEO_ACCEPT}
              multiple
              style={{ display: "none" }}
              onChange={handleFileChange}
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
        )}
      </div>

      {mode === "playlists" ? (
        <VideoPlaylistManager />
      ) : (
      <>
      {/* Suggestions de catégories partagées (import + drawer) : les catégories
          déjà utilisées dans la bibliothèque, sans rien imposer — l'utilisateur
          peut toujours en saisir une nouvelle. */}
      <datalist id="library-programs">
        {availablePrograms.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>

      {/* Dynamic Toast Notifications */}
      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.type === "success" && <Icon name="check_circle" size={20} color="var(--accent-success)" filled />}
          {toast.type === "error" && <Icon name="error" size={20} color="var(--accent-error)" filled />}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Import / Upload Section — affichée uniquement au survol glisser-déposer ou quand des fichiers sont prêts */}
      {(dragActive || pendingSpecs.length > 0) && (
      <div 
        className={`upload-zone ${dragActive ? "drag-active" : ""}`}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => {
          if (pendingSpecs.length === 0 && fileInputRef.current) {
            fileInputRef.current.click();
          }
        }}
      >
        {pendingSpecs.length === 0 ? (
          <>
            <Icon name="cloud_upload" size={48} className="upload-icon" />
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: "8px 0 4px" }}>
              {t("library.uploadDropHint")}
            </h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
              {t("library.uploadFormatsHint")}
            </p>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "4px" }}>
              Plusieurs fichiers acceptés simultanément
            </p>
          </>
        ) : (
            <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", maxWidth: "680px", textAlign: "left" }}
          >
            <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "12px", color: "var(--accent-primary)", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px" }}>
              {pendingSpecs.length} fichier{pendingSpecs.length > 1 ? "s" : ""} sélectionné{pendingSpecs.length > 1 ? "s" : ""} — personnalisez les cours
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxHeight: "380px", overflowY: "auto", paddingRight: "4px" }}>
              {pendingSpecs.map((spec) => (
                <div key={spec.key} style={{ background: "var(--bg-surface-hover)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "12px 14px", display: "flex", flexDirection: "column", gap: "10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
                      <Icon name="movie" size={18} style={{ color: "var(--accent-primary)", flexShrink: 0 }} />
                      <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={spec.file!.name}>
                        {spec.file!.name}
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        ({(spec.file!.size / (1024 * 1024)).toFixed(1)} Mo)
                      </span>
                    </div>
                    <button onClick={() => removePendingSpec(spec.key)} className="olc-press" style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", flexShrink: 0, display: "flex", padding: "4px" }} title="Retirer ce fichier">
                      <Icon name="close" size={16} />
                    </button>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 100px", gap: "8px" }}>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="Titre du cours"
                      value={spec.title}
                      onChange={(e) => updatePendingSpec(spec.key, { title: e.target.value })}
                      style={{ padding: "6px 10px", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text"
                      list="library-programs"
                      className="form-control"
                      placeholder={t("library.programPlaceholder")}
                      value={spec.program ?? ""}
                      onChange={(e) => updatePendingSpec(spec.key, { program: e.target.value })}
                      style={{ padding: "6px 8px", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text"
                      className="form-control"
                      placeholder={t("library.releasePlaceholderExample")}
                      value={spec.release ?? ""}
                      onChange={(e) => updatePendingSpec(spec.key, { release: e.target.value })}
                      style={{ padding: "6px 8px", fontSize: "0.85rem" }}
                    />
                  </div>

                  {/* Synopsis / Description multi-lignes */}
                  <textarea
                    className="form-control"
                    placeholder="Description / Synopsis du cours (optionnel, style Netflix...)"
                    value={spec.description ?? ""}
                    onChange={(e) => updatePendingSpec(spec.key, { description: e.target.value })}
                    rows={2}
                    style={{ fontSize: "0.82rem", resize: "vertical", minHeight: "52px", lineHeight: "1.4" }}
                  />

                  {/* Sous-titres attachés */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px", paddingTop: "6px", borderTop: "1px dashed var(--border-color)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>Sous-titres :</span>
                      {(!spec.subtitles || spec.subtitles.length === 0) ? (
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontStyle: "italic" }}>Aucun</span>
                      ) : (
                        spec.subtitles.map((subFile, idx) => (
                          <span key={idx} className="badge-pill" style={{ display: "inline-flex", alignItems: "center", gap: "4px", background: "rgba(var(--accent-primary-rgb, 99, 102, 241), 0.15)", border: "1px solid var(--accent-primary)", fontSize: "0.74rem", padding: "2px 8px" }}>
                            <Icon name="subtitles" size={12} />
                            <span>{subFile.name}</span>
                            <button
                              type="button"
                              onClick={() => {
                                const newSubs = (spec.subtitles ?? []).filter((_, i) => i !== idx);
                                updatePendingSpec(spec.key, { subtitles: newSubs });
                              }}
                              style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0 2px" }}
                            >
                              <Icon name="close" size={12} />
                            </button>
                          </span>
                        ))
                      )}
                    </div>
                    <label className="btn btn-secondary olc-press" style={{ height: "26px", padding: "0 8px", fontSize: "0.74rem", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      <Icon name="add" size={14} />
                      <span>Ajouter .srt</span>
                      <input
                        type="file"
                        accept=".srt,.vtt,text/vtt,application/x-subrip"
                        style={{ display: "none" }}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) {
                            const newSubs = [...(spec.subtitles ?? []), file];
                            updatePendingSpec(spec.key, { subtitles: newSubs });
                          }
                          e.target.value = "";
                        }}
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: "12px", marginTop: "14px" }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={submitPendingUploads}
                style={{ flex: 1, height: "44px" }}
              >
                Lancer {pendingSpecs.length} upload{pendingSpecs.length > 1 ? "s" : ""}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setPendingSpecs([])}
                style={{ height: "44px" }}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => fileInputRef.current?.click()}
                style={{ height: "44px", whiteSpace: "nowrap" }}
              >
                + Ajouter
              </button>
            </div>
          </div>
        )}
      </div>
      )}

      {/* Barre d'actions groupées */}
      {selectedIds.size > 0 && (
        <div className="interrupted-block">
          <div className="interrupted-text">
            <span className="interrupted-label">{t("library.selectionLabel")}</span>
            <span className="interrupted-title">{t("library.selectedCount", { count: selectedIds.size })}</span>
          </div>
          <div className="interrupted-actions">
            <button className="btn btn-secondary" onClick={() => setShowAddToPlaylist(true)}>
              {t("library.addToPlaylist")}
            </button>
            <button className="btn btn-danger" onClick={() => setBulkDeleteConfirm(true)}>
              {t("common.delete")}
            </button>
            <button className="btn btn-secondary" onClick={clearSelection}>
              {t("library.clearSelection")}
            </button>
          </div>
        </div>
      )}

      {/* Toolbar / Search / Filters */}
      <div className="library-toolbar sticky-glass-toolbar">
        <div className="toolbar-filters">
          <input
            type="text"
            className="search-input"
            placeholder={t("library.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <button
            type="button"
            className="btn btn-secondary mobile-filter-toggle-btn"
            style={{ padding: "8px 12px", fontSize: "0.82rem" }}
            onClick={() => setMobileFiltersOpen((v) => !v)}
          >
            <Icon name="tune" size={18} />
          </button>

          <div className={`toolbar-secondary-filters ${mobileFiltersOpen ? "open" : ""}`}>
            <select
              className="filter-select"
              value={programFilter}
              onChange={(e) => setProgramFilter(e.target.value)}
            >
              <option value="">{t("library.allPrograms")}</option>
              {availablePrograms.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>

            <input
              type="text"
              className="search-input"
              style={{ width: "120px" }}
              placeholder={t("library.releasePlaceholder")}
              value={releaseFilter}
              onChange={(e) => setReleaseFilter(e.target.value)}
            />

            <select
              className="filter-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="imported_at">{t("library.sortImportDate")}</option>
              <option value="title">{t("library.sortTitle")}</option>
              <option value="duration">{t("library.sortDuration")}</option>
            </select>
          </div>
        </div>

        {/* Grid / List view toggle */}
        <div className="view-toggle">
          <button
            className={`view-btn olc-press ${viewMode === "grid" ? "active" : ""}`}
            onClick={() => setViewMode("grid")}
            title={t("library.gridView")}
          >
            <Icon name="grid_view" size={18} />
          </button>
          <button
            className={`view-btn olc-press ${viewMode === "list" ? "active" : ""}`}
            onClick={() => setViewMode("list")}
            title={t("library.listView")}
          >
            <Icon name="view_list" size={18} />
          </button>
        </div>
      </div>

      {/* Main library listing */}
      {loading ? (
        <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
          {t("library.loadingLibrary")}
        </div>
      ) : videos.length === 0 ? (
        <div style={{ display: "flex", flex: 1, flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
          <Icon name="video_library" size={48} color="var(--border-focus)" style={{ marginBottom: "12px" }} />
          <p style={{ margin: 0, fontWeight: 600 }}>{t("library.noVideosFound")}</p>
          <p style={{ fontSize: "0.85rem", margin: "4px 0 0" }}>{t("library.noVideosHint")}</p>
        </div>
      ) : viewMode === "grid" ? (
        /* GRID VIEW — regroupée dynamiquement par catégorie présente : "" = bucket « sans catégorie », placé
           en dernier ; les autres triées sans casse. */
        <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
          {Array.from(new Set(videos.map((v) => (v.program && v.program.trim() ? v.program : ""))))
            .sort((a, b) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b, "fr", { sensitivity: "base" })))
            .map((program) => ({
              program,
              items: videos.filter((v) => (v.program && v.program.trim() ? v.program : "") === program),
            }))
            .filter((g) => g.items.length > 0)
            .map((group) => (
              <div key={group.program}>
                {/* Couleur du thème plutôt que du programme. La case coche
                    tout le groupe d'un coup. */}
                <h3
                  style={{
                    fontSize: "0.85rem",
                    marginBottom: "16px",
                    color: "var(--accent-primary)",
                  }}
                >
                  <label style={{ display: "inline-flex", alignItems: "center", gap: "8px", cursor: "pointer" }} title={t("library.selectGroupTitle")}>
                    <input
                      type="checkbox"
                      checked={allSelected(group.items.map((v) => v.id))}
                      onChange={(e) => setManySelected(group.items.map((v) => v.id), e.target.checked)}
                      style={{ width: "16px", height: "16px", cursor: "pointer" }}
                    />
                    <span>
                      {group.program === "" ? t("library.noProgram") : group.program}{" "}
                      <span style={{ color: "var(--text-dim)" }}>({group.items.length})</span>
                    </span>
                  </label>
                </h3>
                <div className="videos-grid">
                  {group.items.map((video) => {
                    const thumbSrc = getThumbnailSrc(video);
                    const isSelected = selectedIds.has(video.id);
                    return (
                      <div
                        key={video.id}
                        className={`video-card ${getProgramClass(video.program)}${isSelected ? " selected" : ""}`}
                        onClick={() => handleSelectVideo(video)}
                      >
                        <div className="thumbnail-wrapper">
                          <input
                            type="checkbox"
                            className="card-select-checkbox"
                            checked={isSelected}
                            onClick={(e) => e.stopPropagation()}
                            onChange={() => toggleSelected(video.id)}
                          />
                          {thumbSrc ? (
                            <img src={thumbSrc} alt={video.title} className="card-thumbnail" />
                          ) : (
                            <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                              <Icon name="movie" size={32} style={{ opacity: 0.2 }} />
                            </div>
                          )}
                          <span className="card-duration">{formatDuration(video.duration_seconds)}</span>
                        </div>
                        <div className="card-content">
                          <h4 className="card-title" title={video.title}>
                            {video.title}
                          </h4>
                          <div className="card-meta-row">
                            <span className={`program-badge ${getProgramBadgeClass(video.program)}`}>
                              {video.program || t("library.noProgram")}
                            </span>
                            {video.release && (
                              <span className="release-badge">{t("library.releaseBadge", { release: video.release })}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
        </div>
      ) : (
        /* LIST VIEW */
        <div className="table-wrapper">
          <table className="videos-table">
            <thead>
              <tr>
                <th style={{ width: "36px" }}>
                  <input
                    type="checkbox"
                    checked={allSelected(videos.map((v) => v.id))}
                    onChange={(e) => setManySelected(videos.map((v) => v.id), e.target.checked)}
                    title={t("library.selectAllTitle")}
                    style={{ width: "18px", height: "18px", cursor: "pointer" }}
                  />
                </th>
                <th style={{ width: "80px" }}>{t("library.thumbnailHeader")}</th>
                <th>{t("library.titleHeader")}</th>
                <th>{t("library.programHeader")}</th>
                <th>{t("library.releaseHeader")}</th>
                <th>{t("library.durationHeader")}</th>
                <th>{t("library.formatHeader")}</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((video, index) => {
                const thumbSrc = getThumbnailSrc(video);
                return (
                  <tr key={video.id} className={selectedIds.has(video.id) ? "row-selected" : ""} onClick={() => handleSelectVideo(video)}>
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(video.id)}
                        onChange={() => {}}
                        onClick={(e) => handleRowCheckboxClick(e, index, video.id)}
                        title={t("library.selectAllTitle")}
                        style={{ width: "18px", height: "18px", cursor: "pointer" }}
                      />
                    </td>
                    <td>
                      {thumbSrc ? (
                        <img src={thumbSrc} alt="" className="table-thumb" />
                      ) : (
                        <div className="table-thumb" style={{ background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Icon name="movie" size={16} style={{ opacity: 0.2 }} />
                        </div>
                      )}
                    </td>
                    <td style={{ fontWeight: 700, color: "var(--text-main)" }}>
                      {video.title}
                    </td>
                    <td>
                      <span className={`program-badge ${getProgramBadgeClass(video.program)}`}>
                        {video.program || t("library.noProgram")}
                      </span>
                    </td>
                    <td>{video.release ? t("library.releaseFull", { release: video.release }) : "-"}</td>
                    <td>{formatDuration(video.duration_seconds)}</td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {video.width && video.height ? `${video.width}x${video.height}` : ""} {video.codec ? `(${video.codec})` : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Course Studio Modal (Zero-scroll 2-column layout) */}
      {selectedVideo && (
        <div className="course-studio-overlay" onClick={handleCloseDrawer}>
          <div className="course-studio-modal" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="course-studio-header">
              <div style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
                <div className="course-studio-icon-badge">
                  <Icon name="movie_filter" size={22} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "var(--accent-primary)", letterSpacing: "0.08em" }}>
                    Studio d&apos;édition du cours
                  </div>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {drawerTitle || selectedVideo.title}
                  </h2>
                </div>
              </div>
              <button className="close-btn olc-press" onClick={handleCloseDrawer} aria-label={t("common.close")}>
                <Icon name="close" size={20} />
              </button>
            </div>

            {/* Body : 2 colonnes */}
            <div className="course-studio-body">
              {/* Colonne Gauche : Aperçu vidéo, miniature, specs techniques et actions média */}
              <div className="course-studio-col-left">
                <div className="drawer-video-container" style={{ borderRadius: "12px", overflow: "hidden" }}>
                  <video
                    key={selectedVideo.id}
                    className="drawer-video"
                    controls
                    playsInline
                    preload="metadata"
                    crossOrigin="anonymous"
                    src={videoStreamUrl(getApiUrl, selectedVideo.id)}
                    poster={getThumbnailSrc(selectedVideo) || undefined}
                  >
                    {studioSubtitles.map((sub, i) => (
                      <track
                        key={sub.id}
                        kind="subtitles"
                        src={getApiUrl(sub.vtt_url)}
                        srcLang={sub.language_code}
                        label={sub.language_label}
                        default={i === 0}
                      />
                    ))}
                  </video>
                  <WebRenditionPanel key={selectedVideo.id} videoId={selectedVideo.id} />
                </div>

                {/* Miniature & Changement */}
                <div className="course-studio-thumb-row">
                  <div className="course-studio-thumb-preview">
                    {getThumbnailSrc(selectedVideo) ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={getThumbnailSrc(selectedVideo)!} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    ) : (
                      <Icon name="movie" size={24} style={{ opacity: 0.3 }} />
                    )}
                  </div>
                  <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "4px" }}>
                    <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                      {t("library.thumbnailFieldLabel")}
                    </span>
                    <button
                      type="button"
                      className="btn btn-secondary olc-press"
                      style={{ height: "36px", fontSize: "0.82rem", alignSelf: "flex-start" }}
                      onClick={() => thumbnailInputRef.current?.click()}
                      disabled={isUploadingThumbnail}
                    >
                      <Icon name="image" size={16} />
                      <span>{isUploadingThumbnail ? t("common.saving") : t("library.changeThumbnail")}</span>
                    </button>
                    <input
                      ref={thumbnailInputRef}
                      type="file"
                      accept="image/*"
                      style={{ display: "none" }}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadThumbnail(file);
                        e.target.value = "";
                      }}
                    />
                  </div>
                </div>

                {/* Specs Bento */}
                <div className="course-studio-specs-grid">
                  <div className="course-studio-spec-item">
                    <span className="spec-label">{t("library.resolutionLabel")}</span>
                    <span className="spec-val">
                      {selectedVideo.width && selectedVideo.height ? `${selectedVideo.width}x${selectedVideo.height}` : t("library.unknownValue")}
                      {getResolutionBadge(selectedVideo.width, selectedVideo.height) ? ` (${getResolutionBadge(selectedVideo.width, selectedVideo.height)})` : ""}
                    </span>
                  </div>
                  <div className="course-studio-spec-item">
                    <span className="spec-label">{t("library.audioQualityLabel")}</span>
                    <span className="spec-val">
                      {getAudioQualityBadge(selectedVideo.audio_channels, selectedVideo.audio_codec)}
                    </span>
                  </div>
                  <div className="course-studio-spec-item">
                    <span className="spec-label">{t("library.framerateLabel")} / Codec</span>
                    <span className="spec-val">
                      {selectedVideo.fps ? formatFps(selectedVideo.fps) : "--"} • {selectedVideo.codec || "H264"}
                    </span>
                  </div>
                  <div className="course-studio-spec-item">
                    <span className="spec-label">{t("library.bitrateLabel")}</span>
                    <span className="spec-val">
                      {selectedVideo.bitrate_kbps ? formatBitrate(selectedVideo.bitrate_kbps) : "--"}
                    </span>
                  </div>
                  <div className="course-studio-spec-item" style={{ gridColumn: "span 2" }}>
                    <span className="spec-label">Emplacement sur disque</span>
                    <span className="spec-val" style={{ fontSize: "0.74rem", opacity: 0.8, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={selectedVideo.file_path}>
                      {selectedVideo.file_path}
                    </span>
                  </div>
                </div>

                {/* Actions Média (Normalisation + Suppression) */}
                <div style={{ display: "flex", gap: "10px", marginTop: "auto" }}>
                  <button
                    type="button"
                    className="btn btn-secondary olc-press"
                    onClick={handleNormalize}
                    style={{ flex: 1, height: "40px", fontSize: "0.82rem" }}
                    title={t("library.normalizeTitle")}
                  >
                    <Icon name="tune" size={16} />
                    <span>{t("library.normalize")}</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger olc-press"
                    onClick={() => triggerDelete(selectedVideo)}
                    style={{ height: "40px", fontSize: "0.82rem", padding: "0 14px" }}
                  >
                    <Icon name="delete" size={16} />
                    <span>{t("common.delete")}</span>
                  </button>
                </div>
              </div>

              {/* Colonne Droite : Formulaire métadonnées & Sous-titres */}
              <div className="course-studio-col-right">
                <form onSubmit={handleSaveMetadata} style={{ display: "flex", flexDirection: "column", gap: "14px", height: "100%" }}>
                  <div className="form-group">
                    <label className="form-label">{t("library.courseTitleFieldLabel")}</label>
                    <input
                      type="text"
                      className="form-control"
                      value={drawerTitle}
                      onChange={(e) => setDrawerTitle(e.target.value)}
                      required
                      placeholder="Ex: RPM 111 Masterclass"
                      style={{ fontSize: "0.95rem", fontWeight: 600, padding: "10px 14px" }}
                    />
                  </div>

                  <div style={{ display: "flex", gap: "12px" }}>
                    <div className="form-group" style={{ flex: 1, minWidth: 0 }}>
                      <label className="form-label">{t("library.programLabel")}</label>
                      <input
                        type="text"
                        list="library-programs"
                        className="form-control"
                        value={drawerProgram}
                        onChange={(e) => setDrawerProgram(e.target.value)}
                        placeholder={t("library.programPlaceholder")}
                      />
                    </div>

                    <div className="form-group" style={{ width: "130px", minWidth: 0 }}>
                      <label className="form-label">{t("library.releaseLabel")}</label>
                      <input
                        type="text"
                        className="form-control"
                        value={drawerRelease}
                        onChange={(e) => setDrawerRelease(e.target.value)}
                        placeholder={t("library.releasePlaceholderExample")}
                      />
                    </div>
                  </div>

                  <div className="form-group" style={{ flex: "1 1 auto", minHeight: "120px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <label className="form-label">{t("library.descriptionFieldLabel")}</label>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                        Style Netflix • Multi-lignes supporté
                      </span>
                    </div>
                    <textarea
                      className="form-control"
                      value={drawerDescription}
                      onChange={(e) => setDrawerDescription(e.target.value)}
                      placeholder={t("library.descriptionPlaceholder")}
                      style={{ resize: "vertical", minHeight: "110px", maxHeight: "200px", lineHeight: "1.5", fontSize: "0.88rem" }}
                    />
                  </div>

                  {/* Section Sous-titres Studio */}
                  <div className="course-studio-subtitles-section">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Icon name="subtitles" size={18} style={{ color: "var(--accent-primary)" }} />
                        <span style={{ fontSize: "0.82rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          Sous-titres synchronisés
                        </span>
                        <span className="badge-pill" style={{ background: "rgba(255,255,255,0.08)", fontSize: "0.72rem", padding: "2px 6px" }}>
                          {studioSubtitles.length} piste{studioSubtitles.length > 1 ? "s" : ""}
                        </span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <input
                          ref={subtitleInputRef}
                          type="file"
                          accept=".srt,.vtt,text/vtt,application/x-subrip"
                          style={{ display: "none" }}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleUploadSubtitle(file);
                            e.target.value = "";
                          }}
                        />
                        <button
                          type="button"
                          className="btn btn-secondary olc-press"
                          style={{ height: "30px", padding: "0 10px", fontSize: "0.78rem" }}
                          onClick={() => subtitleInputRef.current?.click()}
                        >
                          <Icon name="add" size={14} />
                          <span>Ajouter (.srt, .vtt)</span>
                        </button>
                      </div>
                    </div>

                    {studioSubtitles.length === 0 ? (
                      <div style={{ padding: "12px", textAlign: "center", background: "rgba(0,0,0,0.15)", borderRadius: "8px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        Aucun sous-titre pour ce cours. Glissez ou ajoutez un fichier .srt (ex: cours.fr.srt).
                      </div>
                    ) : (
                      <div className="course-studio-subtitles-list">
                        {studioSubtitles.map((sub) => (
                          <div key={sub.id} className="course-studio-subtitle-tag">
                            <span style={{ fontWeight: 800, textTransform: "uppercase", fontSize: "0.72rem", background: "var(--accent-primary)", color: "#fff", padding: "1px 5px", borderRadius: "4px" }}>
                              {sub.language_code}
                            </span>
                            <span>{sub.language_label}</span>
                            <button
                              type="button"
                              onClick={() => handleDeleteSubtitle(sub.id)}
                              style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0 2px", display: "flex", alignItems: "center" }}
                              title="Supprimer ce sous-titre"
                            >
                              <Icon name="close" size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Boutons validation / enregistrement */}
                  <div style={{ display: "flex", gap: "10px", marginTop: "auto", paddingTop: "8px" }}>
                    <button
                      type="button"
                      className="btn btn-secondary olc-press"
                      onClick={handleCloseDrawer}
                      style={{ height: "44px", padding: "0 18px", fontSize: "0.88rem" }}
                    >
                      {t("common.close")}
                    </button>
                    <button
                      type="submit"
                      className="btn btn-primary olc-press"
                      style={{ flex: 1, height: "44px", fontSize: "0.88rem" }}
                      disabled={isSavingDrawer}
                    >
                      <Icon name="save" size={18} />
                      <span>{isSavingDrawer ? t("common.saving") : t("common.save")}</span>
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Delete Modal */}
      {showDeleteConfirm && videoToDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>
              {t("library.deleteVideoTitle")}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("library.deleteVideoConfirmBefore")}{" "}
              <strong style={{ color: "var(--text-main)" }}>{videoToDelete.title}</strong>
              {t("library.deleteVideoConfirmAfter")}
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setVideoToDelete(null);
                }}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ backgroundColor: "var(--accent-error)" }}
                onClick={confirmDelete}
              >
                {t("library.confirmDelete")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Bulk Delete Modal */}
      {bulkDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>
              {t("library.deleteBulkTitle", { count: selectedIds.size })}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("library.deleteBulkConfirm")}
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setBulkDeleteConfirm(false)}>
                {t("common.cancel")}
              </button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={confirmBulkDelete}>
                {t("library.confirmDelete")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ajout groupé à une playlist */}
      {showAddToPlaylist && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>
              {t("library.addToPlaylistTitle", { count: selectedIds.size })}
            </h3>
            <select className="form-control" value={bulkTargetPlaylistId} onChange={(e) => setBulkTargetPlaylistId(e.target.value)}>
              <option value="">{t("library.choosePlaylist")}</option>
              {playlists.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            {playlists.length === 0 && (
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
                {t("library.noPlaylistsHint")}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setShowAddToPlaylist(false);
                  setBulkTargetPlaylistId("");
                }}
              >
                {t("common.cancel")}
              </button>
              <button type="button" className="btn btn-primary" onClick={confirmBulkAddToPlaylist} disabled={!bulkTargetPlaylistId}>
                {t("library.add")}
              </button>
            </div>
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
}
