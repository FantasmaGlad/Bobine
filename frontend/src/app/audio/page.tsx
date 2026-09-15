"use client";

import React, { useEffect, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useUploadManager } from "@/lib/UploadManager";
import { parseMediaName } from "@/lib/parseMediaName";
import Icon from "@/components/Icon";
import AudioPlaylistManager from "@/components/AudioPlaylistManager";

const AUDIO_EXTENSIONS = [".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"];
const AUDIO_ACCEPT = ".mp3,.m4a,.wav,.aac,.flac,.ogg,audio/*";

const isAudioFile = (f: File) => {
  const lower = f.name.toLowerCase();
  return AUDIO_EXTENSIONS.some((ext) => lower.endsWith(ext));
};

// FileSystemEntry (webkitGetAsEntry) n'est pas dans le lib DOM de TypeScript
// — ce sont les types minimaux réellement utilisés ici.
interface FileEntryLike {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file: (cb: (f: File) => void) => void;
  createReader?: () => { readEntries: (cb: (entries: FileEntryLike[]) => void) => void };
}

/** Lit récursivement un FileSystemEntry (fichier OU dossier) en liste de
 * fichiers audio — réf. mission "importer un dossier complet et l'avoir
 * sous un même cours" : un dossier glissé-déposé n'expose pas directement
 * ses fichiers via `DataTransfer.files` (juste une entrée dossier vide côté
 * navigateur), il faut le parcourir via cette API asynchrone dédiée.
 * `readEntries` est plafonné à ~100 résultats par appel par le navigateur :
 * on boucle jusqu'à une liste vide. */
async function readEntryRecursively(entry: FileEntryLike): Promise<File[]> {
  if (entry.isFile) {
    return new Promise((resolve) => entry.file((f) => resolve(isAudioFile(f) ? [f] : [])));
  }
  if (entry.isDirectory && entry.createReader) {
    const reader = entry.createReader();
    const allEntries: FileEntryLike[] = [];
    for (;;) {
      const batch: FileEntryLike[] = await new Promise((resolve) => reader.readEntries(resolve));
      if (batch.length === 0) break;
      allEntries.push(...batch);
    }
    const nested = await Promise.all(allEntries.map(readEntryRecursively));
    return nested.flat();
  }
  return [];
}

/** Rassemble les fichiers audio d'un DataTransfer glissé-déposé, dossier(s)
 * inclus, et déduit le nom du cours du dossier de plus haut niveau s'il y en
 * a un — sinon (fichiers isolés glissés directement) `folderName` est null
 * et l'appelant retombe sur son heuristique par fichier. */
async function collectDroppedAudioFiles(dataTransfer: DataTransfer): Promise<{ files: File[]; folderName: string | null }> {
  const items = dataTransfer.items;
  if (!items || items.length === 0 || typeof items[0]?.webkitGetAsEntry !== "function") {
    return { files: Array.from(dataTransfer.files).filter(isAudioFile), folderName: null };
  }
  const entries = Array.from(items)
    .map((item) => item.webkitGetAsEntry() as FileEntryLike | null)
    .filter((e): e is FileEntryLike => e !== null);
  const folderEntry = entries.find((e) => e.isDirectory);
  const nested = await Promise.all(entries.map(readEntryRecursively));
  return { files: nested.flat(), folderName: folderEntry?.name ?? null };
}

interface AudioTrack {
  id: number;
  number: number | null;
  title: string;
  duration_seconds: number | null;
  position: number;
  background_id?: number | null;
  background_title?: string | null;
  background_is_image?: boolean;
}

interface AudioCourseSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  background_id: number | null;
  background_thumbnail_path: string | null;
  track_count: number;
  total_duration_seconds: number;
}

interface AudioCourseDetail extends AudioCourseSummary {
  tracks: AudioTrack[];
}

interface BackgroundOption {
  id: number;
  title: string;
  thumbnail_path?: string | null;
  is_image?: boolean;
}

interface AudioPlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
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

function formatDuration(seconds: number | null) {
  if (!seconds) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// Catégories libres (réf. correctif "retire les presets Rpm/Sprint/The
// Trip") : plus de couleur par programme, une seule classe générique suffit
// (même simplification déjà faite côté Bibliothèque vidéo).
function programBadgeClass(_program: string | null) {
  return "autre";
}

function programCardClass(_program: string | null) {
  return "program-autre";
}

export default function AudioLibraryPage() {
  const { t } = useAppSettings();
  // Bascule Cours/Playlists (réf. mission "supprimer la catégorie playlist
  // du volet ouvrant, déplacer la création de playlist audio coach dans
  // Coach > Cours audio") : la création d'éditions mixées vit désormais ici
  // plutôt que sur une page /audio-playlists séparée.
  const [mode, setMode] = useState<"courses" | "playlists">("courses");
  const [courses, setCourses] = useState<AudioCourseSummary[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);
  // Catégories (programmes) réellement présentes parmi les cours audio, pour
  // les suggestions de saisie libre (réf. correctif "retire les presets
  // Rpm/Sprint/The Trip") — même pattern que la Bibliothèque vidéo.
  const [programs, setPrograms] = useState<string[]>([]);

  const [selected, setSelected] = useState<AudioCourseDetail | null>(null);
  const [drawerTitle, setDrawerTitle] = useState("");
  const [drawerProgram, setDrawerProgram] = useState("");
  const [drawerRelease, setDrawerRelease] = useState("");
  const [drawerBackgroundId, setDrawerBackgroundId] = useState<string>("");
  const [showBackgroundPicker, setShowBackgroundPicker] = useState(false);
  const [defaultCoachBgId, setDefaultCoachBgId] = useState<number | null>(null);
  const [savingDrawer, setSavingDrawer] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const [toDelete, setToDelete] = useState<AudioCourseSummary | null>(null);

  const [uploadMode, setUploadMode] = useState<"files" | "zip">("files");
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadZip, setUploadZip] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadProgram, setUploadProgram] = useState("");
  const [uploadRelease, setUploadRelease] = useState("");
  const [dragActive, setDragActive] = useState(false);

  const [pickingTrackBackgroundId, setPickingTrackBackgroundId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const assignTrackBackground = async (trackId: number, bgId: number | null) => {
    if (!selected) return;
    try {
      const res = await fetch(getApiUrl(`/audio/${selected.id}/tracks/${trackId}`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          background_id: bgId,
          clear_background: bgId === null,
        }),
      });
      if (res.ok) {
        const updatedTrack = await res.json();
        setSelected({
          ...selected,
          tracks: selected.tracks.map((t) => (t.id === trackId ? updatedTrack : t)),
        });
        showToast(t("audio.updatedToast"));
      } else {
        showToast(t("audio.saveError"), "error");
      }
    } catch {
      showToast(t("audio.connectionError"), "error");
    } finally {
      setPickingTrackBackgroundId(null);
      setShowBackgroundPicker(false);
    }
  };

  // Réf. mission "queue en direct des importations + import parallèle" :
  // l'import d'un cours (plusieurs MP3 ou une archive ZIP) est désormais
  // envoyé à la file globale d'imports puis le formulaire se réinitialise
  // immédiatement — l'ancienne version désactivait tout le formulaire
  // (`disabled={uploading}`) jusqu'à la fin de l'import, empêchant de
  // préparer/lancer un second cours en attendant que le premier termine.
  const { addUploads, uploads } = useUploadManager();
  const seenDoneIds = useRef<Set<string>>(new Set());
  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => (u.kind === "audio_files" || u.kind === "audio_zip") && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    fetchCourses();
    fetchPrograms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploads]);

  const showToast = (message: string, type: ToastState["type"] = "success") => setToast({ message, type });

  const selectedBg = backgrounds.find((b) => String(b.id) === String(drawerBackgroundId));
  const defaultBg = defaultCoachBgId ? backgrounds.find((b) => b.id === defaultCoachBgId) : null;

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  const fetchCourses = async () => {
    setLoading(true);
    try {
      const res = await fetch(getApiUrl("/audio"), { cache: "no-store" });
      if (res.ok) setCourses(await res.json());
      else showToast(t("audio.fetchError"), "error");
    } catch {
      showToast(t("audio.connectionError"), "error");
    } finally {
      setLoading(false);
    }
  };

  const fetchBackgrounds = async () => {
    try {
      const res = await fetch(getApiUrl("/backgrounds"), { cache: "no-store" });
      if (res.ok) setBackgrounds(await res.json());
    } catch {
      // silencieux : l'association de fond animé reste optionnelle
    }
  };

  const fetchPrograms = () => {
    fetch(getApiUrl("/audio/programs"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: string[]) => setPrograms(Array.isArray(data) ? data : []))
      .catch(() => {});
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial, même motif que library/playlists/schedule
    fetchCourses();
    fetchBackgrounds();
    fetchPrograms();
    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data.default_coach_background_id === "number") {
          setDefaultCoachBgId(data.default_coach_background_id);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCourse = async (courseId: number) => {
    const res = await fetch(getApiUrl(`/audio/${courseId}`), { cache: "no-store" });
    if (!res.ok) {
      showToast(t("audio.loadCourseError"), "error");
      return;
    }
    const detail: AudioCourseDetail = await res.json();
    setSelected(detail);
    setDrawerTitle(detail.title);
    setDrawerProgram(detail.program || "");
    setDrawerRelease(detail.release || "");
    setDrawerBackgroundId(detail.background_id ? String(detail.background_id) : "");
  };

  const closeDrawer = () => setSelected(null);

  const saveMetadata = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    setSavingDrawer(true);
    try {
      const res = await fetch(getApiUrl(`/audio/${selected.id}`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: drawerTitle,
          program: drawerProgram || null,
          release: drawerRelease || null,
          background_id: drawerBackgroundId ? Number(drawerBackgroundId) : null,
          clear_background: !drawerBackgroundId,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelected(updated);
        showToast(t("audio.updatedToast"));
        fetchCourses();
        fetchPrograms();
      } else {
        showToast(t("audio.saveError"), "error");
      }
    } finally {
      setSavingDrawer(false);
    }
  };

  const persistOrder = async (tracks: AudioTrack[]) => {
    if (!selected) return;
    await fetch(getApiUrl(`/audio/${selected.id}/tracks/reorder`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track_ids: tracks.map((t) => t.id) }),
    });
  };

  const handleDrop = (index: number) => {
    if (!selected || dragIndex === null || dragIndex === index) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    const reordered = [...selected.tracks];
    const [moved] = reordered.splice(dragIndex, 1);
    reordered.splice(index, 0, moved);
    setSelected({ ...selected, tracks: reordered });
    setDragIndex(null);
    setDragOverIndex(null);
    persistOrder(reordered);
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      const res = await fetch(getApiUrl(`/audio/${toDelete.id}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("audio.deletedToast"));
        setCourses((prev) => prev.filter((c) => c.id !== toDelete.id));
        if (selected?.id === toDelete.id) setSelected(null);
      } else {
        showToast(t("audio.deleteError"), "error");
      }
    } finally {
      setToDelete(null);
    }
  };

  const resetUpload = () => {
    setUploadFiles([]);
    setUploadZip(null);
    setUploadTitle("");
    setUploadRelease("");
  };

  /**
   * `folderNameHint` : nom du dossier d'origine quand les fichiers viennent
   * d'un import de dossier (glissé-déposé via collectDroppedAudioFiles, ou
   * sélecteur natif webkitdirectory) — réf. mission "importer un dossier
   * complet et l'avoir sous un même cours". Dans ce cas le nom du DOSSIER
   * sert à déduire catégorie/édition (aussi fiable que le nom d'une archive
   * ZIP), plutôt que le nom d'une piste individuelle au hasard.
   */
  const handleFilesSelected = (files: FileList | File[] | null, folderNameHint?: string | null) => {
    if (!files || files.length === 0) return;
    if (uploadMode === "zip") {
      const zip = Array.from(files).find((f) => f.name.toLowerCase().endsWith(".zip")) || files[0];
      setUploadZip(zip);
      const { title, program, release } = parseMediaName(zip.name, programs);
      setUploadTitle(title);
      if (!uploadProgram && program) setUploadProgram(program);
      if (!uploadRelease && release) setUploadRelease(release);
    } else {
      const audioFiles = Array.from(files).filter(isAudioFile);
      setUploadFiles(audioFiles);
      if (audioFiles.length && !uploadTitle) {
        // webkitRelativePath ("Dossier/sous-dossier/piste.mp3") : posé
        // automatiquement par le navigateur pour un <input webkitdirectory>,
        // absent pour une sélection de fichiers isolés.
        const relPath = (audioFiles[0] as File & { webkitRelativePath?: string }).webkitRelativePath;
        const folderName = folderNameHint || (relPath ? relPath.split("/")[0] : null);

        if (folderName) {
          const { title, program, release } = parseMediaName(folderName, programs);
          setUploadTitle(title);
          if (!uploadProgram && program) setUploadProgram(program);
          if (!uploadRelease && release) setUploadRelease(release);
          return;
        }

        // Pas de dossier connu : repli piste par piste (réf. bug "chiffre
        // random affiché sur la tablette" + "cours importés séparément
        // libellisés sous le nom d'un morceau au lieu de Sans catégorie").
        // Le mot qui précède un nombre dans le nom d'UNE piste isolée
        // ("Squat 12.mp3") n'a aucune raison d'être une vraie catégorie —
        // on n'auto-remplit la catégorie que si elle correspond à une
        // catégorie DÉJÀ existante ; sinon le champ reste vide et le cours
        // atterrit dans le groupe "Sans catégorie" existant plutôt que d'en
        // inventer une nouvelle.
        const { title, program, release } = parseMediaName(audioFiles[0].name, programs);
        const isKnownProgram = program && programs.some((p) => p.toLowerCase() === program.toLowerCase());
        if (isKnownProgram && release) {
          setUploadTitle(title);
          if (!uploadProgram) setUploadProgram(program);
          if (!uploadRelease) setUploadRelease(release);
        } else {
          const baseName = audioFiles[0].name
            .replace(/\.(mp3|m4a|wav|aac|flac|ogg)$/i, "")
            .replace(/^\d+[\s._-]*/, "")
            .split(/[_-]/)[0];
          setUploadTitle(baseName || t("audio.newCourseFallback"));
        }
      }
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (uploadMode === "zip") {
      handleFilesSelected(e.dataTransfer.files);
      return;
    }
    // Mode Fichiers MP3 : parcourt aussi un dossier glissé-déposé (réf.
    // mission "importer un dossier complet et l'avoir sous un même cours")
    // — DataTransfer.items doit être lu de façon SYNCHRONE pendant
    // l'événement (webkitGetAsEntry()), collectDroppedAudioFiles le fait
    // avant sa première attente asynchrone.
    collectDroppedAudioFiles(e.dataTransfer).then(({ files, folderName }) => {
      handleFilesSelected(files, folderName);
    });
  };

  const executeUpload = () => {
    if (!uploadTitle.trim()) {
      showToast(t("audio.titleRequiredWarning"), "warning");
      return;
    }
    if (uploadMode === "files" && uploadFiles.length === 0) {
      showToast(t("audio.selectMp3Warning"), "warning");
      return;
    }
    if (uploadMode === "zip" && !uploadZip) {
      showToast(t("audio.selectZipWarning"), "warning");
      return;
    }

    if (uploadMode === "zip" && uploadZip) {
      addUploads([{ kind: "audio_zip", file: uploadZip, title: uploadTitle.trim(), program: uploadProgram, release: uploadRelease }]);
    } else {
      addUploads([{ kind: "audio_files", files: uploadFiles, title: uploadTitle.trim(), program: uploadProgram, release: uploadRelease }]);
    }
    // Le résultat (succès/échec) est visible en direct dans le panneau
    // d'imports flottant — le formulaire se libère immédiatement pour
    // permettre de préparer/lancer un autre cours sans attendre.
    resetUpload();
  };

  // Regroupement dynamique par catégorie réellement présente (réf. correctif
  // "retire les presets Rpm/Sprint/The Trip") : même logique que la grille de
  // la Bibliothèque vidéo — "" = bucket "sans catégorie", placé en dernier.
  const grouped = Array.from(new Set(courses.map((c) => (c.program && c.program.trim() ? c.program : ""))))
    .sort((a, b) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b, "fr", { sensitivity: "base" })))
    .map((program) => ({
      program,
      courses: courses.filter((c) => (c.program && c.program.trim() ? c.program : "") === program),
    }))
    .filter((g) => g.courses.length > 0);

  const getCourseThumbSrc = (course: AudioCourseSummary) => {
    if (!course.background_thumbnail_path) return null;
    const filename = course.background_thumbnail_path.split("/").pop();
    if (!filename) return null;
    return getApiUrl(`/thumbnails/${filename}`);
  };

  return (
    <div className={`library-container ${mode === "playlists" ? "playlists-mode" : ""}`}>
      {/* Bascule Cours/Playlists : même langage visuel que le bascule
          grille/liste de la Bibliothèque vidéo (.view-toggle). */}
      <div className="view-toggle" style={{ alignSelf: "flex-start" }}>
        <button
          className={`view-btn olc-press ${mode === "courses" ? "active" : ""}`}
          onClick={() => setMode("courses")}
        >
          <Icon name="library_music" size={16} /> {t("audio.coursesTab")}
        </button>
        <button
          className={`view-btn olc-press ${mode === "playlists" ? "active" : ""}`}
          onClick={() => setMode("playlists")}
        >
          <Icon name="playlist_play" size={16} /> {t("audio.playlistsTab")}
        </button>
      </div>

      {mode === "playlists" ? (
        <AudioPlaylistManager />
      ) : (
      <>
      {/* Suggestions de catégories déjà utilisées (réf. correctif "retire les
          presets Rpm/Sprint/The Trip") : saisie libre + suggestions, comme la
          Bibliothèque vidéo. */}
      <datalist id="audio-programs">
        {programs.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>

      {toast && (
        <div className={`toast ${toast.type}`}>
          <span>{toast.message}</span>
        </div>
      )}

      <div
        className={`upload-zone ${dragActive ? "drag-active" : ""}`}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleFileDrop}
        onClick={() => uploadFiles.length === 0 && !uploadZip && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={uploadMode === "zip" ? ".zip" : AUDIO_ACCEPT}
          multiple={uploadMode === "files"}
          style={{ display: "none" }}
          onChange={(e) => {
            handleFilesSelected(e.target.files);
            e.target.value = "";
          }}
        />
        {/* Import d'un dossier complet (réf. mission "importer un dossier
            complet et l'avoir sous un même cours") : webkitdirectory n'est
            pas dans le typage DOM standard de React, posé directement sur le
            noeud DOM plutôt qu'en JSX typé. */}
        <input
          ref={(el) => {
            folderInputRef.current = el;
            // webkitdirectory/directory : attributs non typés par React/TS,
            // posés directement sur le noeud DOM une fois monté.
            if (el) {
              el.setAttribute("webkitdirectory", "");
              el.setAttribute("directory", "");
            }
          }}
          type="file"
          multiple
          style={{ display: "none" }}
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            const relPath = (files[0] as (File & { webkitRelativePath?: string }) | undefined)?.webkitRelativePath;
            handleFilesSelected(files, relPath ? relPath.split("/")[0] : null);
            e.target.value = "";
          }}
        />

        {uploadFiles.length === 0 && !uploadZip ? (
          <>
            <div className="view-toggle" onClick={(e) => e.stopPropagation()} style={{ marginBottom: "8px" }}>
              <button
                type="button"
                className={`view-btn ${uploadMode === "files" ? "active" : ""}`}
                onClick={() => setUploadMode("files")}
              >
                {t("audio.mp3Files")}
              </button>
              <button
                type="button"
                className={`view-btn ${uploadMode === "zip" ? "active" : ""}`}
                onClick={() => setUploadMode("zip")}
              >
                {t("audio.zipArchive")}
              </button>
            </div>
            <Icon name="cloud_upload" size={48} className="upload-icon" />
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: "8px 0 4px" }}>
              {uploadMode === "files" ? t("audio.dropMp3Hint") : t("audio.dropZipHint")}
            </h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
              {t("audio.trackOrderHint")}
            </p>
            {uploadMode === "files" && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ marginTop: "12px" }}
                onClick={(e) => {
                  e.stopPropagation();
                  folderInputRef.current?.click();
                }}
              >
                <Icon name="folder_open" size={16} />
                {t("audio.importFolder")}
              </button>
            )}
          </>
        ) : (
          <div onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: "500px", textAlign: "left" }}>
            <div className="form-group">
              <label className="form-label">{t("audio.courseNameLabel")}</label>
              <input type="text" className="form-control" value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} />
            </div>
            <div style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">{t("audio.programLabel")}</label>
                <input
                  type="text"
                  list="audio-programs"
                  className="form-control"
                  placeholder={t("audio.programPlaceholder")}
                  value={uploadProgram}
                  onChange={(e) => setUploadProgram(e.target.value)}
                />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">{t("audio.releaseLabel")}</label>
                <input type="text" className="form-control" placeholder={t("audio.releasePlaceholder")} value={uploadRelease} onChange={(e) => setUploadRelease(e.target.value)} />
              </div>
            </div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: "12px 0" }}>
              {uploadMode === "files" ? (
                uploadFiles.length > 1 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                    <span style={{ fontWeight: 700, color: "var(--accent-primary)" }}>
                      {uploadFiles.length} pistes audio sélectionnées
                    </span>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Elles seront regroupées en 1 seul cours audio avec {uploadFiles.length} pistes
                    </span>
                  </div>
                ) : (
                  <span>1 piste audio sélectionnée · 1 cours audio</span>
                )
              ) : (
                t("audio.zipArchiveLabel", { name: uploadZip?.name ?? "" })
              )}
            </div>
            <div style={{ display: "flex", gap: "12px" }}>
              <button type="button" className="btn btn-primary" onClick={executeUpload} style={{ flex: 1, height: "48px" }}>
                {t("audio.startImport")}
              </button>
              <button type="button" className="btn btn-secondary" onClick={resetUpload} style={{ height: "48px" }}>
                {t("common.cancel")}
              </button>
            </div>
          </div>
        )}
      </div>

      {loading ? (
        <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
          {t("audio.loadingCourses")}
        </div>
      ) : courses.length === 0 ? (
        <div style={{ display: "flex", flex: 1, flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" }}>
          <p style={{ margin: 0, fontWeight: 600 }}>{t("audio.noCoursesTitle")}</p>
          <p style={{ fontSize: "0.85rem", margin: "4px 0 0" }}>{t("audio.noCoursesHint")}</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
          {grouped.map((group) => (
            <div key={group.program}>
              {/* Couleur du thème plutôt que du programme (réf. correctif
                  "couleurs hardcodées associées à un cours"). */}
              <h3
                style={{
                  fontSize: "0.85rem",
                  marginBottom: "16px",
                  color: "var(--accent-primary)",
                }}
              >
                {group.program === "" ? t("audio.noProgram") : group.program}{" "}
                <span style={{ color: "var(--text-dim)" }}>({group.courses.length})</span>
              </h3>
              <div className="videos-grid">
                {group.courses.map((course) => {
                  const thumbSrc = getCourseThumbSrc(course);
                  return (
                    <div key={course.id} className={`video-card ${programCardClass(course.program)}`} onClick={() => openCourse(course.id)}>
                      <div className="thumbnail-wrapper" style={{ background: "var(--bg-surface-elevated)" }}>
                        {thumbSrc ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={thumbSrc} alt="" className="card-thumbnail" />
                        ) : (
                          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Icon name="library_music" size={40} style={{ opacity: 0.25 }} />
                          </div>
                        )}
                        <span className="card-duration">{t("audio.tracksCount", { count: course.track_count })}</span>
                      </div>
                      <div className="card-content">
                        <h4 className="card-title" title={course.title}>{course.title}</h4>
                        <div className="card-meta-row">
                          <span className={`program-badge ${programBadgeClass(course.program)}`}>{course.program || t("audio.noProgram")}</span>
                          <span className="release-badge">{formatDuration(course.total_duration_seconds)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <>
          <div className="detail-drawer-overlay" onClick={closeDrawer} />
          <div className="detail-drawer">
            <div className="drawer-header">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", maxWidth: "80%" }}>
                {selected.title}
              </h3>
              <button className="close-btn" onClick={closeDrawer}>
                <Icon name="close" size={20} />
              </button>
            </div>
            <div className="drawer-body">
              <form className="drawer-form" onSubmit={saveMetadata}>
                <h4 style={{ fontSize: "0.85rem", fontWeight: 800, borderBottom: "1px solid var(--border-color)", paddingBottom: "6px", margin: "0 0 8px" }}>
                  {t("audio.metadataSectionTitle")}
                </h4>
                <div className="form-group">
                  <label className="form-label">{t("audio.titleLabel")}</label>
                  <input type="text" className="form-control" value={drawerTitle} onChange={(e) => setDrawerTitle(e.target.value)} required />
                </div>
                <div style={{ display: "flex", gap: "12px" }}>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">{t("audio.programLabel")}</label>
                    <input
                      type="text"
                      list="audio-programs"
                      className="form-control"
                      placeholder={t("audio.programPlaceholder")}
                      value={drawerProgram}
                      onChange={(e) => setDrawerProgram(e.target.value)}
                    />
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">{t("audio.releaseLabel")}</label>
                    <input type="text" className="form-control" value={drawerRelease} onChange={(e) => setDrawerRelease(e.target.value)} />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">{t("audio.backgroundAssociationLabel")}</label>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      background: "var(--bg-surface-elevated)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "var(--radius-md)",
                      padding: "8px 12px",
                    }}
                  >
                    <div
                      style={{
                        width: "72px",
                        height: "40.5px",
                        borderRadius: "6px",
                        overflow: "hidden",
                        background: "var(--bg-surface-hover)",
                        position: "relative",
                        flexShrink: 0,
                      }}
                    >
                      {selectedBg?.thumbnail_path ? (
                        <img
                          src={getApiUrl(`/thumbnails/${selectedBg.thumbnail_path.split("/").pop()}`)}
                          alt={selectedBg.title}
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                        />
                      ) : defaultBg?.thumbnail_path && !drawerBackgroundId ? (
                        <img
                          src={getApiUrl(`/thumbnails/${defaultBg.thumbnail_path.split("/").pop()}`)}
                          alt={defaultBg.title}
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                        />
                      ) : (
                        <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", opacity: 0.4 }}>
                          <Icon name={drawerBackgroundId ? "image" : "hide_image"} size={20} />
                        </div>
                      )}
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {selectedBg ? selectedBg.title : defaultBg ? `${defaultBg.title} (${t("backgrounds.defaultBadge")})` : t("audio.noBackgroundOption")}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {selectedBg
                          ? (selectedBg.is_image ? "Image fixe personnalisée" : "Boucle vidéo personnalisée")
                          : defaultBg
                          ? t("backgrounds.defaultClubAmbiance")
                          : t("backgrounds.noBackgroundAmbiance")}
                      </div>
                    </div>

                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ height: "34px", padding: "0 10px", fontSize: "0.8rem", whiteSpace: "nowrap" }}
                      onClick={() => setShowBackgroundPicker(true)}
                    >
                      {t("coach.changeAmbianceBtn")}
                    </button>
                  </div>
                </div>

                <h4 style={{ fontSize: "0.85rem", fontWeight: 800, borderBottom: "1px solid var(--border-color)", paddingBottom: "6px", margin: "16px 0 8px" }}>
                  {t("audio.tracksSectionTitle", { count: selected.tracks.length })}
                </h4>
                <div className="drag-drop-zone" style={{ minHeight: "80px" }}>
                  {selected.tracks.map((track, index) => {
                    const trackBg = track.background_id
                      ? backgrounds.find((b) => b.id === track.background_id)
                      : null;
                    return (
                      <div
                        key={track.id}
                        className={`playlist-drag-item ${dragIndex === index ? "dragging" : ""} ${dragOverIndex === index ? "drag-over-item" : ""}`}
                        draggable
                        onDragStart={() => setDragIndex(index)}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragOverIndex(index);
                        }}
                        onDrop={() => handleDrop(index)}
                        onDragEnd={() => {
                          setDragIndex(null);
                          setDragOverIndex(null);
                        }}
                        style={{ display: "flex", alignItems: "center", gap: "10px" }}
                      >
                        <span className="drag-handle"><Icon name="drag_indicator" size={16} /></span>
                        <span style={{ flex: 1, fontWeight: 600, fontSize: "0.88rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {index + 1}. {track.title}
                        </span>

                        <button
                          type="button"
                          className="olc-press"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                            padding: "4px 8px",
                            borderRadius: "6px",
                            background: trackBg ? "color-mix(in srgb, var(--accent-primary) 15%, var(--bg-surface-elevated))" : "var(--bg-surface)",
                            border: `1px solid ${trackBg ? "var(--accent-primary)" : "var(--border-color)"}`,
                            color: trackBg ? "var(--accent-primary)" : "var(--text-muted)",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            cursor: "pointer",
                            flexShrink: 0,
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            setPickingTrackBackgroundId(track.id);
                            setShowBackgroundPicker(true);
                          }}
                          title={trackBg ? `Ambiance piste : ${trackBg.title}` : "Lier une ambiance à cette piste"}
                        >
                          <Icon name={trackBg ? (trackBg.is_image ? "image" : "videocam") : "wallpaper"} size={14} />
                          <span style={{ maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {trackBg ? trackBg.title : "Ambiance auto"}
                          </span>
                        </button>

                        <span style={{ color: "var(--text-muted)", fontSize: "0.8rem", flexShrink: 0 }}>
                          {formatDuration(track.duration_seconds)}
                        </span>
                      </div>
                    );
                  })}
                </div>

                <div className="drawer-actions">
                  <button type="submit" className="btn btn-primary" style={{ flex: 1, height: "48px" }} disabled={savingDrawer}>
                    {savingDrawer ? t("common.saving") : t("common.save")}
                  </button>
                  <button type="button" className="btn btn-danger" style={{ height: "48px" }} onClick={() => setToDelete(selected)}>
                    {t("common.delete")}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}

      {toDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>{t("audio.deleteCourseTitle")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("audio.deleteCourseConfirmBefore")}{" "}
              <strong style={{ color: "var(--text-main)" }}>{toDelete.title}</strong>{" "}
              {t("audio.deleteCourseConfirmAfter", { count: toDelete.track_count })}
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setToDelete(null)}>{t("common.cancel")}</button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={confirmDelete}>
                {t("audio.confirmDelete")}
              </button>
            </div>
          </div>
        </div>
      )}

      {showBackgroundPicker && (
        <div
          className="modal-overlay"
          onClick={() => {
            setShowBackgroundPicker(false);
            setPickingTrackBackgroundId(null);
          }}
        >
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "620px", width: "100%", maxHeight: "85vh", display: "flex", flexDirection: "column" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 800 }}>
                  {pickingTrackBackgroundId
                    ? `Ambiance de la piste`
                    : t("dashboard.chooseAmbiance")}
                </h3>
                {pickingTrackBackgroundId && (
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    Cette ambiance visuelle sera lancée automatiquement dès que cette piste débute
                  </span>
                )}
              </div>
              <button
                className="coach-icon-btn olc-press"
                style={{ width: "36px", height: "36px", fontSize: "0.9rem" }}
                onClick={() => {
                  setShowBackgroundPicker(false);
                  setPickingTrackBackgroundId(null);
                }}
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            <div style={{ overflowY: "auto", flex: 1, paddingRight: "4px" }}>
              {pickingTrackBackgroundId ? (
                /* Option piste : Hériter de l'ambiance du cours */
                <div
                  className="olc-press"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    background: !selected?.tracks.find((t) => t.id === pickingTrackBackgroundId)?.background_id ? "var(--bg-surface-hover)" : "var(--bg-surface-elevated)",
                    border: `1.5px solid ${!selected?.tracks.find((t) => t.id === pickingTrackBackgroundId)?.background_id ? "var(--accent-primary)" : "var(--border-color)"}`,
                    cursor: "pointer",
                    marginBottom: "14px",
                  }}
                  onClick={() => assignTrackBackground(pickingTrackBackgroundId, null)}
                >
                  <div style={{ width: "64px", height: "36px", borderRadius: "4px", background: "var(--bg-surface-hover)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <Icon name="auto_awesome" size={20} color="var(--accent-primary)" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>Ambiance automatique du cours (par défaut)</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Conserver l'ambiance globale choisie pour le cours entier</div>
                  </div>
                  {!selected?.tracks.find((t) => t.id === pickingTrackBackgroundId)?.background_id && (
                    <Icon name="check_circle" size={20} color="var(--accent-primary)" filled />
                  )}
                </div>
              ) : (
                <>
                  {/* Option 1 : Fond par défaut du club (si configuré) */}
                  {defaultBg && (
                    <div
                      className={`olc-press ${!drawerBackgroundId ? "active" : ""}`}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "10px 12px",
                        borderRadius: "8px",
                        background: !drawerBackgroundId ? "var(--bg-surface-hover)" : "var(--bg-surface-elevated)",
                        border: `1.5px solid ${!drawerBackgroundId ? "var(--accent-primary)" : "var(--border-color)"}`,
                        cursor: "pointer",
                        marginBottom: "10px",
                      }}
                      onClick={() => {
                        setDrawerBackgroundId("");
                        setShowBackgroundPicker(false);
                      }}
                    >
                      <div style={{ width: "64px", height: "36px", borderRadius: "4px", overflow: "hidden", background: "var(--bg-surface-hover)", flexShrink: 0 }}>
                        {defaultBg.thumbnail_path ? (
                          <img
                            src={getApiUrl(`/thumbnails/${defaultBg.thumbnail_path.split("/").pop()}`)}
                            alt={defaultBg.title}
                            style={{ width: "100%", height: "100%", objectFit: "cover" }}
                          />
                        ) : (
                          <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Icon name="bookmark" size={18} color="var(--accent-primary)" />
                          </div>
                        )}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: "0.88rem", display: "flex", alignItems: "center", gap: "6px" }}>
                          <span>{defaultBg.title}</span>
                          <span style={{ fontSize: "0.72rem", background: "var(--accent-primary)", color: "var(--accent-primary-fg)", padding: "2px 6px", borderRadius: "4px" }}>
                            {t("backgrounds.defaultBadge")}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          {t("backgrounds.defaultClubAmbiance")}
                        </div>
                      </div>
                      {!drawerBackgroundId && <Icon name="check_circle" size={20} color="var(--accent-primary)" filled />}
                    </div>
                  )}

                  {/* Option 2 : Écran sobre (aucun fond) */}
                  <div
                    className="olc-press"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      padding: "10px 12px",
                      borderRadius: "8px",
                      background: (!defaultBg && !drawerBackgroundId) ? "var(--bg-surface-hover)" : "var(--bg-surface-elevated)",
                      border: `1.5px solid ${(!defaultBg && !drawerBackgroundId) ? "var(--accent-primary)" : "var(--border-color)"}`,
                      cursor: "pointer",
                      marginBottom: "14px",
                    }}
                    onClick={() => {
                      setDrawerBackgroundId("");
                      setShowBackgroundPicker(false);
                    }}
                  >
                    <div style={{ width: "64px", height: "36px", borderRadius: "4px", background: "var(--bg-surface-hover)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <Icon name="hide_image" size={20} style={{ opacity: 0.5 }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>{t("backgrounds.noBackgroundAmbiance")}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Afficher un écran sobre sans boucle visuelle</div>
                    </div>
                    {!defaultBg && !drawerBackgroundId && <Icon name="check_circle" size={20} color="var(--accent-primary)" filled />}
                  </div>
                </>
              )}

              {/* Grille des ambiances disponibles */}
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
                {t("backgrounds.hubTitle")} ({backgrounds.length})
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: "10px" }}>
                {backgrounds.map((bg) => {
                  const activeTrackBgId = pickingTrackBackgroundId
                    ? selected?.tracks.find((t) => t.id === pickingTrackBackgroundId)?.background_id
                    : null;
                  const isSelected = pickingTrackBackgroundId
                    ? activeTrackBgId === bg.id
                    : String(bg.id) === String(drawerBackgroundId);
                  const thumb = bg.thumbnail_path
                    ? getApiUrl(`/thumbnails/${bg.thumbnail_path.split("/").pop()}`)
                    : null;
                  return (
                    <div
                      key={bg.id}
                      className="olc-press"
                      style={{
                        background: isSelected ? "var(--bg-surface-hover)" : "var(--bg-surface-elevated)",
                        border: `2px solid ${isSelected ? "var(--accent-primary)" : "var(--border-color)"}`,
                        borderRadius: "8px",
                        overflow: "hidden",
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                      }}
                      onClick={() => {
                        if (pickingTrackBackgroundId) {
                          assignTrackBackground(pickingTrackBackgroundId, bg.id);
                        } else {
                          setDrawerBackgroundId(String(bg.id));
                          setShowBackgroundPicker(false);
                        }
                      }}
                    >
                      <div style={{ width: "100%", aspectRatio: "16/9", background: "var(--bg-surface-hover)", position: "relative" }}>
                        {thumb ? (
                          <img src={thumb} alt={bg.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                        ) : (
                          <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Icon name={bg.is_image ? "image" : "videocam"} size={22} style={{ opacity: 0.4 }} />
                          </div>
                        )}
                        {isSelected && (
                          <div style={{ position: "absolute", top: 4, right: 4, background: "var(--accent-primary)", borderRadius: "50%", width: "20px", height: "20px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Icon name="check" size={14} color="var(--accent-primary-fg)" />
                          </div>
                        )}
                      </div>
                      <div style={{ padding: "6px 8px", fontSize: "0.78rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={bg.title}>
                        {bg.title}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "16px" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setShowBackgroundPicker(false);
                  setPickingTrackBackgroundId(null);
                }}
              >
                {t("common.close")}
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
