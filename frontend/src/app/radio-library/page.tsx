"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useUploadManager } from "@/lib/UploadManager";
import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import { matchesQuery } from "@/lib/searchText";
import ResponsiveSelect from "@/components/ResponsiveSelect";

// Bibliothèque musicale Radio — écran unique « vue d'ensemble » (refonte).
// Barre latérale persistante (playlists / tags / genres / artistes, tous
// cliquables pour filtrer) + grille principale avec sélection multiple et
// actions groupées (taguer, ajouter à une playlist, supprimer). L'import est
// une modale (bouton dans la barre) plutôt qu'une zone géante au milieu. Les
// tags s'attribuent par clics (chips) dans le drawer d'un morceau ou en lot ;
// les playlists se réordonnent en glisser-déposer.

interface RadioTrack {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
  album_artist: string | null;
  track_number: number | null;
  disc_number: number | null;
  year: number | null;
  genre: string | null;
  duration_seconds: number | null;
  has_cover: boolean;
  tags: string[];
}

interface PlaylistSummary {
  id: number;
  name: string;
  is_default: boolean;
  item_count: number;
  total_duration_seconds: number;
  cover_track_id: number | null;
}

interface PlaylistItem {
  id: number;
  position: number;
  track: { id: number; title: string; artist: string | null; album: string | null; duration_seconds: number | null; has_cover: boolean };
}

interface PlaylistDetail {
  id: number;
  name: string;
  is_default: boolean;
  items: PlaylistItem[];
  total_duration_seconds: number;
}

interface ArtistEntry { name: string; track_count: number; album_count: number; }
interface AlbumEntry { album: string; album_artist: string | null; track_count: number; year: number | null; cover_track_id: number | null; }
interface TagEntry { id: number; name: string; track_count: number; }

type Filter = { type: "artist" | "album" | "genre" | "tag" | "playlist"; value: string } | null;

/** Sections de la barre de navigation horizontale. */
type Section = "tracks" | "playlists" | "artists" | "tags" | "import";
type SortKey = "recent" | "title" | "artist" | "duration";
type ViewMode = "grid" | "list";
const VIEW_STORAGE_KEY = "bobine.radioLibrary.view";

interface ToastState { message: string; type: "success" | "error" | "warning"; }

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

// Extensions audio acceptées (miroir de AUDIO_EXTENSIONS côté backend) : sert
// à filtrer les fichiers non-audio quand on importe un DOSSIER entier
// (webkitdirectory renvoie tout le contenu, sous-dossiers compris).
const AUDIO_EXTENSIONS = [
  ".mp3", ".m4a", ".aac", ".mp4", ".ogg", ".oga", ".opus", ".webm", ".flac",
  ".wav", ".wma", ".aiff", ".aif", ".aifc", ".ape", ".alac", ".wv", ".mka", ".m4b", ".ac3",
];
const isAudioFile = (name: string) => AUDIO_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext));

export default function RadioLibraryPage() {
  const { t } = useAppSettings();

  const [tracks, setTracks] = useState<RadioTrack[]>([]);
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [artists, setArtists] = useState<ArtistEntry[]>([]);
  const [albums, setAlbums] = useState<AlbumEntry[]>([]);
  const [tagsList, setTagsList] = useState<TagEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [coverVersion, setCoverVersion] = useState(0);

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>(null);
  const [section, setSection] = useState<Section>("tracks");
  const [sortKey, setSortKey] = useState<SortKey>("recent");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [artistsView, setArtistsView] = useState<"artists" | "albums">("artists");
  // Morceaux de la playlist utilisée comme filtre (chargés au clic sur « Voir les morceaux »).
  const [playlistFilterIds, setPlaylistFilterIds] = useState<Set<number> | null>(null);

  // Vue grille ou liste mémorisée par appareil (accès au stockage protégé : il peut être indisponible).
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(VIEW_STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture unique d'une préférence locale après hydratation
      if (stored === "grid" || stored === "list") setViewMode(stored);
    } catch {
      // stockage indisponible : vue grille
    }
  }, []);
  const chooseViewMode = (mode: ViewMode) => {
    setViewMode(mode);
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, mode);
    } catch {
      // la préférence reste valable pour cette session
    }
  };

  // Sélection multiple + actions groupées
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkMenu, setBulkMenu] = useState<null | "tag" | "playlist">(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  // Import (section « Importer »)
  // ZIP et pistes partagent désormais le même sélecteur générique
  // (détecté après coup à la sélection, cf. startFilesUpload) — seul le
  // dossier a encore besoin d'un mode dédié (sélecteur natif différent,
  // webkitdirectory).
  const [uploadMode, setUploadMode] = useState<"files" | "folder">("files");
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Édition d'un morceau
  const [selectedTrack, setSelectedTrack] = useState<RadioTrack | null>(null);
  const [form, setForm] = useState({
    title: "", artist: "", album: "", album_artist: "",
    track_number: "", disc_number: "", year: "", genre: "",
  });
  const [drawerTags, setDrawerTags] = useState<string[]>([]);
  const [newChip, setNewChip] = useState("");
  const [savingDrawer, setSavingDrawer] = useState(false);
  const [toDelete, setToDelete] = useState<RadioTrack | null>(null);
  const coverInputRef = useRef<HTMLInputElement>(null);

  // Playlists
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [editingPlaylist, setEditingPlaylist] = useState<PlaylistDetail | null>(null);
  const [addTrackSearch, setAddTrackSearch] = useState("");
  const [playlistToDelete, setPlaylistToDelete] = useState<PlaylistSummary | null>(null);
  const [addingTrackId, setAddingTrackId] = useState<number | null>(null);
  const dragIndexRef = useRef<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  // Sérialise toutes les mutations d'UNE playlist (ajout/retrait/renommage/
  // réordonnancement) : chacune part de l'état serveur le plus frais plutôt
  // que d'une valeur capturée au moment du clic, et attend son tour derrière
  // la précédente. Sans ça, un blur de renommage (PUT snapshot des items) et
  // un clic "Ajouter" (POST) peuvent partir en parallèle ; celui qui répond
  // en second écrase le résultat de l'autre — un ajout pouvait disparaître
  // silencieusement.
  const playlistMutationRef = useRef<Promise<unknown>>(Promise.resolve());
  const editingPlaylistRef = useRef<PlaylistDetail | null>(null);
  useEffect(() => { editingPlaylistRef.current = editingPlaylist; }, [editingPlaylist]);

  // Tags
  const [newTagName, setNewTagName] = useState("");

  const { uploads, addUploads } = useUploadManager();
  const seenDoneIds = useRef<Set<string>>(new Set());

  const showToast = (message: string, type: ToastState["type"] = "success") => setToast({ message, type });
  // Imports radio en cours ou récents, affichés dans la section « Importer ».
  const radioUploads = uploads.filter((u) => u.kind === "radio_files" || u.kind === "radio_zip").slice(-12).reverse();

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  const fetchJson = async <T,>(path: string, fallback: T): Promise<T> => {
    try {
      const res = await fetch(getApiUrl(path), { cache: "no-store" });
      return res.ok ? await res.json() : fallback;
    } catch {
      return fallback;
    }
  };

  const refreshAll = async () => {
    setLoading(true);
    const [tr, pl, ar, al, tg] = await Promise.all([
      fetchJson<RadioTrack[]>("/radio/tracks", []),
      fetchJson<PlaylistSummary[]>("/radio/playlists", []),
      fetchJson<ArtistEntry[]>("/radio/artists", []),
      fetchJson<AlbumEntry[]>("/radio/albums", []),
      fetchJson<TagEntry[]>("/radio/tags", []),
    ]);
    setTracks(tr); setPlaylists(pl); setArtists(ar); setAlbums(al); setTagsList(tg);
    setLoading(false);
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial, même motif que les autres pages bibliothèque
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => (u.kind === "radio_files" || u.kind === "radio_zip") && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploads]);

  const trackCoverUrl = (id: number) => `${getApiUrl(`/radio/tracks/${id}/cover`)}?v=${coverVersion}`;

  // ---- Import ----
  // `webkitdirectory` est posé/retiré juste avant `click()`, dans le même
  // gestionnaire (pas via un effet React) : entre un `setUploadMode(...)` et
  // le re-rendu qui suivrait, `click()` ouvrirait le sélecteur natif AVANT
  // que l'attribut n'ait eu le temps d'être appliqué — l'utilisateur verrait
  // le mauvais type de sélecteur (fichiers au lieu de dossier ou l'inverse).
  const openFilesPicker = () => {
    setUploadMode("files");
    const el = fileInputRef.current;
    if (!el) return;
    el.removeAttribute("webkitdirectory");
    el.removeAttribute("directory");
    el.click();
  };

  const openFolderPicker = (e: React.MouseEvent) => {
    e.stopPropagation();
    setUploadMode("folder");
    const el = fileInputRef.current;
    if (!el) return;
    el.setAttribute("webkitdirectory", "");
    el.setAttribute("directory", "");
    el.click();
  };

  const startFilesUpload = (fileList: FileList | null, modeOverride?: "files" | "folder") => {
    if (!fileList || fileList.length === 0) return;
    // `modeOverride` pour le dépôt glisser-déposer (cf. handleFileDrop) : un
    // setUploadMode() juste avant cet appel n'aurait pas encore été appliqué
    // (état React asynchrone) au moment où cette fonction lit `uploadMode`.
    const mode = modeOverride ?? uploadMode;
    let files = Array.from(fileList);
    if (mode === "folder") {
      files = files.filter((f) => isAudioFile(f.name));
      if (files.length === 0) {
        showToast(t("radioLibrary.noAudioInFolder"), "warning");
        if (fileInputRef.current) fileInputRef.current.value = "";
        return;
      }
      // UNE tâche par morceau : comme les vidéos, chaque fichier a sa propre ligne de
      // progression dans le panneau d'import, au lieu d'un seul lot opaque.
      // L'endpoint /radio/tracks/upload accepte une liste — un fichier par
      // requête crée un job d'import distinct, donc un suivi 1-par-1.
      addUploads(files.map((f) => ({ kind: "radio_files" as const, files: [f], title: f.name })));
    } else if (files.length === 1 && files[0].name.toLowerCase().endsWith(".zip")) {
      // Une seule archive ZIP sélectionnée/déposée : détectée automatiquement,
      // pas besoin d'un mode dédié.
      addUploads([{ kind: "radio_zip", file: files[0], title: files[0].name }]);
    } else {
      // Idem sélection multiple de fichiers : une tâche (donc une ligne de
      // suivi) par morceau.
      addUploads(files.map((f) => ({ kind: "radio_files" as const, files: [f], title: f.name })));
    }
    showToast(t("radioLibrary.importStarted"));
    if (fileInputRef.current) fileInputRef.current.value = "";
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
    // Un dépôt glisser-déposer n'est jamais le résultat du sélecteur dossier
    // natif (webkitdirectory) — toujours des fichiers à plat, quel que soit
    // le dernier mode utilisé au clic (cf. modeOverride, évite le décalage
    // d'un setUploadMode() asynchrone).
    startFilesUpload(e.dataTransfer.files, "files");
  };

  // ---- Édition d'un morceau ----
  const openTrack = (track: RadioTrack) => {
    setSelectedTrack(track);
    setForm({
      title: track.title,
      artist: track.artist ?? "",
      album: track.album ?? "",
      album_artist: track.album_artist ?? "",
      track_number: track.track_number != null ? String(track.track_number) : "",
      disc_number: track.disc_number != null ? String(track.disc_number) : "",
      year: track.year != null ? String(track.year) : "",
      genre: track.genre ?? "",
    });
    setDrawerTags([...track.tags]);
    setNewChip("");
  };

  const parseIntOrNull = (value: string): number | null => {
    const trimmed = value.trim();
    if (trimmed === "") return null;
    const n = parseInt(trimmed, 10);
    return Number.isNaN(n) ? null : n;
  };

  const toggleDrawerTag = (name: string) => {
    setDrawerTags((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]));
  };
  const addChip = () => {
    const name = newChip.trim();
    if (!name) return;
    setDrawerTags((prev) => (prev.includes(name) ? prev : [...prev, name]));
    setNewChip("");
  };

  const saveMetadata = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTrack || !form.title.trim()) { showToast(t("radioLibrary.saveError"), "warning"); return; }
    setSavingDrawer(true);
    try {
      const res = await fetch(getApiUrl(`/radio/tracks/${selectedTrack.id}`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(), artist: form.artist, album: form.album,
          album_artist: form.album_artist, genre: form.genre,
          track_number: parseIntOrNull(form.track_number),
          disc_number: parseIntOrNull(form.disc_number),
          year: parseIntOrNull(form.year),
          tags: drawerTags,
        }),
      });
      if (res.ok) {
        const updated: RadioTrack = await res.json();
        setSelectedTrack(updated);
        setDrawerTags([...updated.tags]);
        showToast(t("radioLibrary.updatedToast"));
        refreshAll();
      } else showToast(t("radioLibrary.saveError"), "error");
    } catch { showToast(t("radioLibrary.connectionError"), "error"); }
    finally { setSavingDrawer(false); }
  };

  const handleCoverSelected = async (fileList: FileList | null) => {
    if (!selectedTrack || !fileList || fileList.length === 0) return;
    const fd = new FormData();
    fd.append("file", fileList[0]);
    try {
      const res = await fetch(getApiUrl(`/radio/tracks/${selectedTrack.id}/cover`), { method: "POST", body: fd });
      if (res.ok) {
        const updated: RadioTrack = await res.json();
        setSelectedTrack(updated);
        setCoverVersion((v) => v + 1);
        showToast(t("radioLibrary.coverUpdatedToast"));
        refreshAll();
      } else showToast(t("radioLibrary.coverError"), "error");
    } catch { showToast(t("radioLibrary.coverError"), "error"); }
    finally { if (coverInputRef.current) coverInputRef.current.value = ""; }
  };

  const confirmDeleteTrack = async () => {
    if (!toDelete) return;
    try {
      const res = await fetch(getApiUrl(`/radio/tracks/${toDelete.id}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("radioLibrary.deletedToast"));
        if (selectedTrack?.id === toDelete.id) setSelectedTrack(null);
        refreshAll();
      } else showToast(t("radioLibrary.deleteError"), "error");
    } catch { showToast(t("radioLibrary.connectionError"), "error"); }
    finally { setToDelete(null); }
  };

  // ---- Sélection multiple ----
  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const clearSelection = () => { setSelected(new Set()); setBulkMenu(null); };

  const applyTagToSelection = async (name: string, add: boolean) => {
    const targets = tracks.filter((tr) => selected.has(tr.id));
    await Promise.all(targets.map((tr) => {
      const has = tr.tags.includes(name);
      if (add === has) return Promise.resolve();
      const nextTags = add ? [...tr.tags, name] : tr.tags.filter((x) => x !== name);
      return fetch(getApiUrl(`/radio/tracks/${tr.id}`), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags: nextTags }),
      });
    }));
    showToast(t("radioLibrary.tagsAppliedToast"));
    refreshAll();
  };

  const addSelectionToPlaylist = async (playlistId: number) => {
    const detail = await fetchJson<PlaylistDetail | null>(`/radio/playlists/${playlistId}`, null);
    if (!detail) { showToast(t("radioLibrary.playlistError"), "error"); return; }
    const existing = detail.items.map((i) => i.track.id);
    const merged = [...existing];
    selected.forEach((id) => { if (!merged.includes(id)) merged.push(id); });
    try {
      const res = await fetch(getApiUrl(`/radio/playlists/${playlistId}`), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: detail.name, track_ids: merged }),
      });
      if (res.ok) { showToast(t("radioLibrary.bulkAddedToPlaylistToast")); setBulkMenu(null); refreshAll(); }
      else showToast(t("radioLibrary.playlistError"), "error");
    } catch { showToast(t("radioLibrary.playlistError"), "error"); }
  };

  const confirmBulkDelete = async () => {
    const ids = Array.from(selected);
    await Promise.all(ids.map((id) => fetch(getApiUrl(`/radio/tracks/${id}`), { method: "DELETE" }).catch(() => null)));
    showToast(t("radioLibrary.bulkDeletedToast", { count: ids.length }));
    setBulkDeleteOpen(false);
    clearSelection();
    refreshAll();
  };

  // ---- Playlists ----
  // Rafraîchissement léger (compteurs de la barre latérale) après une
  // mutation de playlist — un refreshAll() complet (5 requêtes, tracks/
  // artistes/albums/tags compris) à chaque ajout de morceau provoquait un
  // reflow de toute la page sous le tiroir ouvert, donnant l'impression que
  // le panneau « se refermait sur lui-même ».
  const refreshPlaylistsSummary = async () => {
    setPlaylists(await fetchJson<PlaylistSummary[]>("/radio/playlists", []));
  };

  // Chaîne toutes les mutations d'une même playlist (ajout, retrait,
  // renommage, réordonnancement) les unes après les autres : chacune lit
  // l'état serveur le plus frais (editingPlaylistRef) au moment où elle
  // s'exécute réellement, pas au moment du clic. Évite qu'un renommage
  // (PUT avec un instantané des morceaux) et un ajout (POST) partis en
  // parallèle ne se marchent dessus — celui qui répond en second écrasait
  // silencieusement le résultat de l'autre.
  const queuePlaylistMutation = (fn: () => Promise<void>) => {
    const run = playlistMutationRef.current.then(fn, fn);
    playlistMutationRef.current = run.catch(() => undefined);
    return run;
  };

  const openPlaylist = async (id: number) => {
    const detail = await fetchJson<PlaylistDetail | null>(`/radio/playlists/${id}`, null);
    if (detail) setEditingPlaylist(detail);
    else showToast(t("radioLibrary.playlistError"), "error");
  };

  const createPlaylist = async () => {
    const name = newPlaylistName.trim();
    if (!name) return;
    try {
      const res = await fetch(getApiUrl("/radio/playlists"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, track_ids: [] }),
      });
      if (res.ok) {
        const detail: PlaylistDetail = await res.json();
        setNewPlaylistName("");
        showToast(t("radioLibrary.playlistCreatedToast"));
        setEditingPlaylist(detail);
        refreshPlaylistsSummary();
      } else showToast(t("radioLibrary.playlistError"), "error");
    } catch { showToast(t("radioLibrary.playlistError"), "error"); }
  };

  // Sauvegarde bas niveau (PUT complet nom + morceaux) : n'est plus appelée
  // qu'à travers queuePlaylistMutation ci-dessous, jamais directement, pour
  // que ses écritures restent sérialisées avec les autres mutations.
  const savePlaylist = async (id: number, name: string, trackIds: number[]) => {
    try {
      const res = await fetch(getApiUrl(`/radio/playlists/${id}`), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, track_ids: trackIds }),
      });
      if (res.ok) {
        const detail: PlaylistDetail = await res.json();
        setEditingPlaylist(detail);
        refreshPlaylistsSummary();
        return true;
      }
    } catch { /* fallthrough */ }
    showToast(t("radioLibrary.playlistError"), "error");
    return false;
  };

  const renamePlaylist = (name: string) => {
    queuePlaylistMutation(async () => {
      const current = editingPlaylistRef.current;
      if (!current || current.name === name) return;
      await savePlaylist(current.id, name, current.items.map((i) => i.track.id));
    });
  };

  const removeFromPlaylist = (trackId: number) => {
    queuePlaylistMutation(async () => {
      const current = editingPlaylistRef.current;
      if (!current) return;
      const ids = current.items.map((i) => i.track.id).filter((id) => id !== trackId);
      await savePlaylist(current.id, current.name, ids);
    });
  };

  const addToPlaylist = (trackId: number) => {
    const current = editingPlaylistRef.current;
    if (!current) return;
    setAddingTrackId(trackId);
    queuePlaylistMutation(async () => {
      try {
        const res = await fetch(getApiUrl(`/radio/playlists/${current.id}/tracks`), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ track_id: trackId }),
        });
        if (res.ok) {
          const detail: PlaylistDetail = await res.json();
          setEditingPlaylist(detail);
          refreshPlaylistsSummary();
        } else showToast(t("radioLibrary.playlistError"), "error");
      } catch { showToast(t("radioLibrary.playlistError"), "error"); }
      finally { setAddingTrackId((id) => (id === trackId ? null : id)); }
    });
  };

  // Réordonnancement glisser-déposer (natif HTML5, pas de dépendance).
  const handleItemDrop = (dropIndex: number) => {
    const from = dragIndexRef.current;
    dragIndexRef.current = null;
    setDragOverIndex(null);
    if (from === null || from === dropIndex) return;
    queuePlaylistMutation(async () => {
      const current = editingPlaylistRef.current;
      if (!current) return;
      const ids = current.items.map((i) => i.track.id);
      const [moved] = ids.splice(from, 1);
      ids.splice(dropIndex, 0, moved);
      await savePlaylist(current.id, current.name, ids);
    });
  };

  // Ambiance par défaut PROPRE à chaque sortie radio (câblée, réseau) : un choix facultatif qui
  // prime sur la playlist ★ « par défaut » (inchangée, elle reste le repli des deux sorties).
  // La bibliothèque et les playlists restent uniques — seule la désignation est par sortie.
  const [outputDefaults, setOutputDefaults] = useState<Record<string, { override_playlist_id: number | null; effective_playlist_id: number | null }> | null>(null);
  const loadOutputDefaults = () => {
    fetch(getApiUrl("/radio/default-playlist"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then(setOutputDefaults)
      .catch(() => {});
  };
  useEffect(() => {
    loadOutputDefaults();
  }, []);
  const toggleOutputDefault = async (radioChannel: "radio_cable" | "radio_network") => {
    const current = editingPlaylistRef.current;
    if (!current) return;
    const isChosen = outputDefaults?.[radioChannel]?.override_playlist_id === current.id;
    try {
      const res = await fetch(getApiUrl("/radio/default-playlist"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: radioChannel, playlist_id: isChosen ? null : current.id }),
      });
      if (res.ok) setOutputDefaults(await res.json());
      else showToast(t("radioLibrary.playlistError"), "error");
    } catch { showToast(t("radioLibrary.playlistError"), "error"); }
  };

  const toggleDefault = () => {
    queuePlaylistMutation(async () => {
      const current = editingPlaylistRef.current;
      if (!current) return;
      const method = current.is_default ? "DELETE" : "PUT";
      try {
        const res = await fetch(getApiUrl(`/radio/playlists/${current.id}/default`), { method });
        if (res.ok) {
          const detail: PlaylistDetail = await res.json();
          setEditingPlaylist(detail);
          refreshPlaylistsSummary();
        } else showToast(t("radioLibrary.playlistError"), "error");
      } catch { showToast(t("radioLibrary.playlistError"), "error"); }
    });
  };

  const confirmDeletePlaylist = async () => {
    if (!playlistToDelete) return;
    try {
      const res = await fetch(getApiUrl(`/radio/playlists/${playlistToDelete.id}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("radioLibrary.playlistDeletedToast"));
        if (editingPlaylist?.id === playlistToDelete.id) setEditingPlaylist(null);
        refreshAll();
      } else showToast(t("radioLibrary.playlistError"), "error");
    } catch { showToast(t("radioLibrary.playlistError"), "error"); }
    finally { setPlaylistToDelete(null); }
  };

  // ---- Tags ----
  const createTag = async () => {
    const name = newTagName.trim();
    if (!name) return;
    try {
      const res = await fetch(getApiUrl("/radio/tags"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
      });
      if (res.ok) { setNewTagName(""); showToast(t("radioLibrary.tagCreatedToast")); refreshAll(); }
      else if (res.status === 409) showToast(t("radioLibrary.tagExists"), "warning");
      else showToast(t("radioLibrary.tagError"), "error");
    } catch { showToast(t("radioLibrary.tagError"), "error"); }
  };

  const renameTag = async (tag: TagEntry) => {
    const name = window.prompt(t("radioLibrary.renameTag"), tag.name);
    if (!name || name.trim() === tag.name) return;
    try {
      const res = await fetch(getApiUrl(`/radio/tags/${tag.id}`), {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: name.trim() }),
      });
      if (res.ok) refreshAll(); else showToast(t("radioLibrary.tagError"), "error");
    } catch { showToast(t("radioLibrary.tagError"), "error"); }
  };

  const deleteTag = async (tag: TagEntry) => {
    if (!window.confirm(t("radioLibrary.deleteTagConfirm", { name: tag.name }))) return;
    try {
      const res = await fetch(getApiUrl(`/radio/tags/${tag.id}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("radioLibrary.tagDeletedToast"));
        if (filter?.type === "tag" && filter.value === tag.name) clearFilter();
        refreshAll();
      } else showToast(t("radioLibrary.tagError"), "error");
    } catch { showToast(t("radioLibrary.tagError"), "error"); }
  };

  // Choisir un filtre (artiste, album, tag, style) bascule sur la section Morceaux, où il s'applique.
  const applyFilter = (f: Filter) => { setFilter(f); setPlaylistFilterIds(null); setSection("tracks"); };

  const filterByPlaylist = async (playlist: PlaylistSummary) => {
    const detail = await fetchJson<PlaylistDetail | null>(`/radio/playlists/${playlist.id}`, null);
    if (!detail) { showToast(t("radioLibrary.playlistError"), "error"); return; }
    setPlaylistFilterIds(new Set(detail.items.map((i) => i.track.id)));
    setFilter({ type: "playlist", value: playlist.name });
    setSection("tracks");
  };
  const clearFilter = () => { setFilter(null); setPlaylistFilterIds(null); };

  // ---- Dérivés ----
  const genres = useMemo(() => {
    const map = new Map<string, number>();
    tracks.forEach((tr) => { if (tr.genre) map.set(tr.genre, (map.get(tr.genre) ?? 0) + 1); });
    return Array.from(map.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name));
  }, [tracks]);

  // Autocomplétion : titres, artistes, albums et styles de toute la bibliothèque.
  const trackSuggestions = useMemo(
    () => tracks.flatMap((tr) => [tr.title, tr.artist, tr.album, tr.genre].filter((x): x is string => !!x)),
    [tracks],
  );
  const q = search.trim();
  const filteredTracks = useMemo(() => tracks.filter((tr) => {
    if (q && !matchesQuery(`${tr.title} ${tr.artist ?? ""} ${tr.album ?? ""} ${tr.genre ?? ""}`, q)) return false;
    if (filter) {
      if (filter.type === "artist" && tr.artist !== filter.value && tr.album_artist !== filter.value) return false;
      if (filter.type === "album" && tr.album !== filter.value) return false;
      if (filter.type === "genre" && tr.genre !== filter.value) return false;
      if (filter.type === "tag" && !tr.tags.includes(filter.value)) return false;
      if (filter.type === "playlist" && !(playlistFilterIds?.has(tr.id) ?? false)) return false;
    }
    return true;
  }), [tracks, q, filter, playlistFilterIds]);

  const sortedTracks = useMemo(() => {
    const list = [...filteredTracks];
    const byText = (a: string | null, b: string | null) => (a ?? "").localeCompare(b ?? "", "fr", { sensitivity: "base" });
    if (sortKey === "title") list.sort((a, b) => byText(a.title, b.title));
    else if (sortKey === "artist") list.sort((a, b) => byText(a.artist, b.artist) || byText(a.title, b.title));
    else if (sortKey === "duration") list.sort((a, b) => (b.duration_seconds ?? 0) - (a.duration_seconds ?? 0));
    else list.sort((a, b) => b.id - a.id);
    return list;
  }, [filteredTracks, sortKey]);

  const addableTracks = editingPlaylist
    ? tracks.filter((tr) => {
        return matchesQuery(`${tr.title} ${tr.artist ?? ""} ${tr.album ?? ""}`, addTrackSearch);
      })
    : [];

  const visibleIds = sortedTracks.map((tr) => tr.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selected.has(id));
  const toggleSelectAllVisible = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) visibleIds.forEach((id) => next.delete(id));
      else visibleIds.forEach((id) => next.add(id));
      return next;
    });
  };

  // État tri-valué d'un tag sur la sélection courante (pour le menu de tag en lot).
  const selectionTagState = (name: string): "all" | "some" | "none" => {
    const targets = tracks.filter((tr) => selected.has(tr.id));
    if (targets.length === 0) return "none";
    const withTag = targets.filter((tr) => tr.tags.includes(name)).length;
    if (withTag === 0) return "none";
    if (withTag === targets.length) return "all";
    return "some";
  };

  const filterLabel = filter ? filter.value : t("radioLibrary.allTracks");

  // ---- Rendu : carte morceau ----
  const trackCard = (track: RadioTrack) => {
    const isSel = selected.has(track.id);
    return (
      <div key={track.id} className={`video-card rl-card ${isSel ? "selected" : ""}`} onClick={() => openTrack(track)}>
        <button
          type="button"
          className={`rl-card-check ${isSel ? "on" : ""}`}
          title={t("radioLibrary.select")}
          onClick={(e) => { e.stopPropagation(); toggleSelect(track.id); }}
        >
          <Icon name={isSel ? "check_circle" : "radio_button_unchecked"} size={20} filled={isSel} />
        </button>
        <div className="thumbnail-wrapper rl-thumb">
          {track.has_cover ? (
            // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
            <img src={trackCoverUrl(track.id)} alt="" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            <Icon name="music_note" size={40} style={{ opacity: 0.25 }} />
          )}
          <span className="card-duration">{formatDuration(track.duration_seconds)}</span>
        </div>
        <div className="card-content">
          <h4 className="card-title" title={track.title}>{track.title}</h4>
          <div className="card-meta-row">
            <span className="rl-card-artist">{track.artist || t("radioLibrary.unknownArtist")}</span>
          </div>
          {track.tags.length > 0 && (
            <div className="rl-card-tags">
              {track.tags.slice(0, 3).map((tg) => <span key={tg} className="rl-card-tag">{tg}</span>)}
              {track.tags.length > 3 && <span className="rl-card-tag">+{track.tags.length - 3}</span>}
            </div>
          )}
        </div>
      </div>
    );
  };

  // Carte morceau en vue LISTE (dense, pour les grosses bibliothèques).
  const trackRow = (track: RadioTrack) => {
    const isSel = selected.has(track.id);
    return (
      <div key={track.id} className={`rl-list-row ${isSel ? "selected" : ""}`} onClick={() => openTrack(track)}>
        <button
          type="button"
          className={`rl-list-check ${isSel ? "on" : ""}`}
          title={t("radioLibrary.select")}
          aria-pressed={isSel}
          onClick={(e) => { e.stopPropagation(); toggleSelect(track.id); }}
        >
          <Icon name={isSel ? "check_circle" : "radio_button_unchecked"} size={20} filled={isSel} />
        </button>
        <span className="rl-list-cover">
          {track.has_cover ? (
            // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
            <img src={trackCoverUrl(track.id)} alt="" loading="lazy" />
          ) : <Icon name="music_note" size={18} style={{ opacity: 0.3 }} />}
        </span>
        <span className="rl-list-text">
          <span className="rl-list-title">{track.title}</span>
          <span className="rl-list-sub">{track.artist || t("radioLibrary.unknownArtist")}{track.album ? ` — ${track.album}` : ""}</span>
        </span>
        {track.genre ? <span className="rl-list-genre">{track.genre}</span> : <span className="rl-list-genre rl-list-genre--empty" />}
        <span className="rl-list-tags">
          {track.tags.slice(0, 2).map((tg) => <span key={tg} className="rl-card-tag">{tg}</span>)}
          {track.tags.length > 2 && <span className="rl-card-tag">+{track.tags.length - 2}</span>}
        </span>
        <span className="rl-list-duration">{formatDuration(track.duration_seconds)}</span>
      </div>
    );
  };

  const filterIcon = filter
    ? (filter.type === "tag" ? "label" : filter.type === "genre" ? "graphic_eq" : filter.type === "playlist" ? "queue_music" : filter.type === "album" ? "album" : "person")
    : "library_music";

  const sectionButton = (id: Section, icon: string, label: string, count?: number) => (
    <button
      key={id}
      type="button"
      role="tab"
      aria-selected={section === id}
      className={`display-output-btn olc-press ${section === id ? "active" : ""}`}
      onClick={() => setSection(id)}
    >
      <Icon name={icon} size={16} />
      {label}
      {count !== undefined && <span className="rl-tab-count">{count}</span>}
    </button>
  );

  return (
    <div className="radio-lib radio-lib--tabs">
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}

      {/* ==================== BARRE DE NAVIGATION HORIZONTALE (même style que « Sortie Câblé ») ==================== */}
      <div className="live-block channel-card rl-nav-card">
        <div className="channel-card-left">
          <h3>
            <Icon name="library_music" size={18} />
            {t("radioLibrary.title")}
          </h3>
          <span className="status-pill neutral">{t("radioLibrary.countLabel", { count: tracks.length })}</span>
        </div>
        <div className="channel-card-right">
          <div className="display-output-switch rl-sections" role="tablist" aria-label={t("radioLibrary.sectionsLabel")}>
            <div className="display-output-buttons">
              {sectionButton("tracks", "library_music", t("radioLibrary.sectionTracks"), tracks.length)}
              {sectionButton("playlists", "queue_music", t("radioLibrary.sectionPlaylists"), playlists.length)}
              {sectionButton("artists", "person", t("radioLibrary.sectionArtists"), artists.length)}
              {sectionButton("tags", "label", t("radioLibrary.sectionTags"), tagsList.length + genres.length)}
              {sectionButton("import", "cloud_upload", t("radioLibrary.sectionImport"))}
            </div>
          </div>
        </div>
      </div>

      <main className="radio-lib-main"
        onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleFileDrop}>
        {dragActive && (
          <div className="rl-drop-overlay"><Icon name="cloud_upload" size={40} /><span>{t("radioLibrary.dropHere")}</span></div>
        )}

        {/* ---------------- Section MORCEAUX ---------------- */}
        {section === "tracks" && (
          <>
            {selected.size === 0 ? (
              <div className="rl-toolbar sticky-glass-toolbar">
                <div className="rl-search-wrap">
                  <SearchBox
                    className="search-input rl-search"
                    placeholder={t("radioLibrary.searchPlaceholder")}
                    value={search}
                    onChange={setSearch}
                    suggestions={trackSuggestions}
                  />
                </div>
                {filter && (
                  <div className="rl-filter-chip">
                    <Icon name={filterIcon} size={16} />
                    <span>{filter.value}</span>
                    <button type="button" onClick={clearFilter} title={t("radioLibrary.clearFilter")}><Icon name="close" size={14} /></button>
                  </div>
                )}
                <span className="rl-count">{t("radioLibrary.countLabel", { count: sortedTracks.length })}</span>
                <div className="rl-toolbar-spacer" />
                <ResponsiveSelect
                  className="filter-select"
                  value={sortKey}
                  onChange={(value) => setSortKey(value as SortKey)}
                  title={t("radioLibrary.sortLabel")}
                  searchable={false}
                  options={[
                    { value: "recent", label: t("radioLibrary.sortRecent") },
                    { value: "title", label: t("radioLibrary.sortTitle") },
                    { value: "artist", label: t("radioLibrary.sortArtist") },
                    { value: "duration", label: t("radioLibrary.sortDuration") },
                  ]}
                />
                <div className="view-toggle" role="group" aria-label={t("radioLibrary.viewLabel")}>
                  <button type="button" className={`view-btn ${viewMode === "grid" ? "active" : ""}`} onClick={() => chooseViewMode("grid")} title={t("radioLibrary.viewGrid")} aria-pressed={viewMode === "grid"}>
                    <Icon name="grid_view" size={16} />
                  </button>
                  <button type="button" className={`view-btn ${viewMode === "list" ? "active" : ""}`} onClick={() => chooseViewMode("list")} title={t("radioLibrary.viewList")} aria-pressed={viewMode === "list"}>
                    <Icon name="view_list" size={16} />
                  </button>
                </div>
                {sortedTracks.length > 0 && (
                  <button type="button" className="btn btn-secondary" onClick={toggleSelectAllVisible}>
                    <Icon name="checklist" size={16} /> {allVisibleSelected ? t("radioLibrary.deselectAll") : t("radioLibrary.selectAll")}
                  </button>
                )}
              </div>
            ) : (
              <div className="rl-selection-bar">
                <button type="button" className="rl-sel-close" onClick={clearSelection} title={t("radioLibrary.clearSelection")}><Icon name="close" size={18} /></button>
                <span className="rl-sel-count">{t("radioLibrary.selectionCount", { count: selected.size })}</span>
                <div className="rl-toolbar-spacer" />
                <div className="rl-bulk-wrap">
                  <button type="button" className="btn btn-secondary" onClick={() => setBulkMenu(bulkMenu === "tag" ? null : "tag")}><Icon name="label" size={16} /> {t("radioLibrary.bulkTag")}</button>
                  {bulkMenu === "tag" && (
                    <div className="rl-popover" onClick={(e) => e.stopPropagation()}>
                      <div className="rl-popover-title">{t("radioLibrary.bulkTagTitle")}</div>
                      {tagsList.length === 0 ? <p className="rl-empty-note">{t("radioLibrary.noTags")}</p> : tagsList.map((tag) => {
                        const st = selectionTagState(tag.name);
                        return (
                          <button key={tag.id} type="button" className="rl-popover-item" onClick={() => applyTagToSelection(tag.name, st !== "all")}>
                            <Icon name={st === "all" ? "check_box" : st === "some" ? "indeterminate_check_box" : "check_box_outline_blank"} size={18} />
                            <span>{tag.name}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div className="rl-bulk-wrap">
                  <button type="button" className="btn btn-secondary" onClick={() => setBulkMenu(bulkMenu === "playlist" ? null : "playlist")}><Icon name="playlist_add" size={16} /> {t("radioLibrary.bulkAddToPlaylist")}</button>
                  {bulkMenu === "playlist" && (
                    <div className="rl-popover" onClick={(e) => e.stopPropagation()}>
                      <div className="rl-popover-title">{t("radioLibrary.addToPlaylistTitle")}</div>
                      {playlists.length === 0 ? <p className="rl-empty-note">{t("radioLibrary.noPlaylists")}</p> : playlists.map((p) => (
                        <button key={p.id} type="button" className="rl-popover-item" onClick={() => addSelectionToPlaylist(p.id)}>
                          <Icon name={p.is_default ? "star" : "queue_music"} size={16} filled={p.is_default} />
                          <span>{p.name}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button type="button" className="btn btn-danger" onClick={() => setBulkDeleteOpen(true)}><Icon name="delete" size={16} /> {t("radioLibrary.delete")}</button>
              </div>
            )}

            {loading ? (
              <div className="rl-center-note">{t("radioLibrary.loading")}</div>
            ) : tracks.length === 0 ? (
              <div className="rl-empty-state">
                <Icon name="radio" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
                <p style={{ margin: 0, fontWeight: 600 }}>{t("radioLibrary.empty")}</p>
                <button type="button" className="btn btn-primary" style={{ marginTop: "12px" }} onClick={() => setSection("import")}><Icon name="cloud_upload" size={16} /> {t("radioLibrary.importButton")}</button>
              </div>
            ) : sortedTracks.length === 0 ? (
              <div className="rl-center-note">{t("radioLibrary.noResults")}</div>
            ) : viewMode === "grid" ? (
              <div className="videos-grid rl-grid">{sortedTracks.map(trackCard)}</div>
            ) : (
              <div className="rl-list">{sortedTracks.map(trackRow)}</div>
            )}
          </>
        )}

        {/* ---------------- Section PLAYLISTS ---------------- */}
        {section === "playlists" && (
          <>
            <div className="rl-toolbar sticky-glass-toolbar">
              <div className="rl-create-row rl-create-row--wide">
                <input type="text" className="form-control" placeholder={t("radioLibrary.newPlaylistPlaceholder")} value={newPlaylistName}
                  onChange={(e) => setNewPlaylistName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") createPlaylist(); }} />
                <button type="button" className="btn btn-primary" onClick={createPlaylist} disabled={!newPlaylistName.trim()}>
                  <Icon name="add" size={16} /> {t("radioLibrary.create")}
                </button>
              </div>
              <div className="rl-toolbar-spacer" />
              <span className="rl-count">{t("radioLibrary.playlistsCount", { count: playlists.length })}</span>
            </div>
            {playlists.length === 0 ? (
              <div className="rl-empty-state">
                <Icon name="queue_music" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
                <p style={{ margin: 0, fontWeight: 600 }}>{t("radioLibrary.noPlaylists")}</p>
              </div>
            ) : (
              <div className="rl-cards">
                {playlists.map((p) => (
                  <div key={p.id} className="rl-pcard" role="button" tabIndex={0} onClick={() => openPlaylist(p.id)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openPlaylist(p.id); } }}>
                    <div className="rl-pcard-cover">
                      {p.cover_track_id != null ? (
                        // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
                        <img src={trackCoverUrl(p.cover_track_id)} alt="" loading="lazy" />
                      ) : <Icon name="queue_music" size={36} style={{ opacity: 0.3 }} />}
                      {p.is_default && <span className="rl-pcard-star" title={t("radioLibrary.setDefault")}><Icon name="star" size={14} filled /></span>}
                    </div>
                    <div className="rl-pcard-body">
                      <span className="rl-pcard-title" title={p.name}>{p.name}</span>
                      <span className="rl-pcard-meta">
                        {t("radioLibrary.itemsInPlaylist", { count: p.item_count })} · {formatDuration(p.total_duration_seconds)}
                      </span>
                      <span className="rl-pcard-badges">
                        {outputDefaults?.radio_cable?.override_playlist_id === p.id && <span className="rl-card-tag"><Icon name="cable" size={11} /> {t("radioLibrary.outputCable")}</span>}
                        {outputDefaults?.radio_network?.override_playlist_id === p.id && <span className="rl-card-tag"><Icon name="wifi" size={11} /> {t("radioLibrary.outputNetwork")}</span>}
                      </span>
                    </div>
                    <div className="rl-pcard-actions">
                      <button type="button" className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); filterByPlaylist(p); }}>
                        <Icon name="library_music" size={14} /> {t("radioLibrary.viewTracks")}
                      </button>
                      <button type="button" className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); openPlaylist(p.id); }}>
                        <Icon name="edit" size={14} /> {t("radioLibrary.editPlaylist")}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ---------------- Section ARTISTES & ALBUMS ---------------- */}
        {section === "artists" && (
          <>
            <div className="rl-toolbar sticky-glass-toolbar">
              <div className="view-toggle" role="group">
                <button type="button" className={`view-btn ${artistsView === "artists" ? "active" : ""}`} onClick={() => setArtistsView("artists")}>
                  <Icon name="person" size={16} /> {t("radioLibrary.artistsTitle")}
                </button>
                <button type="button" className={`view-btn ${artistsView === "albums" ? "active" : ""}`} onClick={() => setArtistsView("albums")}>
                  <Icon name="album" size={16} /> {t("radioLibrary.albumsTitle")}
                </button>
              </div>
              <div className="rl-toolbar-spacer" />
              <span className="rl-count">{artistsView === "artists" ? artists.length : albums.length}</span>
            </div>
            {artistsView === "artists" ? (
              artists.length === 0 ? <div className="rl-center-note">{t("radioLibrary.noResults")}</div> : (
                <div className="rl-cards">
                  {artists.map((a) => (
                    <button key={a.name} type="button" className="rl-pcard rl-pcard--simple" onClick={() => applyFilter({ type: "artist", value: a.name })}>
                      <div className="rl-pcard-cover rl-pcard-cover--round"><Icon name="person" size={32} style={{ opacity: 0.35 }} /></div>
                      <div className="rl-pcard-body">
                        <span className="rl-pcard-title" title={a.name}>{a.name}</span>
                        <span className="rl-pcard-meta">{t("radioLibrary.itemsInPlaylist", { count: a.track_count })} · {t("radioLibrary.albumsCount", { count: a.album_count })}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )
            ) : albums.length === 0 ? <div className="rl-center-note">{t("radioLibrary.noResults")}</div> : (
              <div className="rl-cards">
                {albums.map((al) => (
                  <button key={`${al.album}-${al.album_artist ?? ""}`} type="button" className="rl-pcard rl-pcard--simple" onClick={() => applyFilter({ type: "album", value: al.album })}>
                    <div className="rl-pcard-cover">
                      {al.cover_track_id != null ? (
                        // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
                        <img src={trackCoverUrl(al.cover_track_id)} alt="" loading="lazy" />
                      ) : <Icon name="album" size={36} style={{ opacity: 0.3 }} />}
                    </div>
                    <div className="rl-pcard-body">
                      <span className="rl-pcard-title" title={al.album}>{al.album}</span>
                      <span className="rl-pcard-meta">{al.album_artist || t("radioLibrary.unknownArtist")}{al.year ? ` · ${al.year}` : ""} · {t("radioLibrary.itemsInPlaylist", { count: al.track_count })}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        {/* ---------------- Section TAGS & STYLES ---------------- */}
        {section === "tags" && (
          <>
            <div className="rl-toolbar sticky-glass-toolbar">
              <div className="rl-create-row rl-create-row--wide">
                <input type="text" className="form-control" placeholder={t("radioLibrary.newTagPlaceholder")} value={newTagName}
                  onChange={(e) => setNewTagName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") createTag(); }} />
                <button type="button" className="btn btn-primary" onClick={createTag} disabled={!newTagName.trim()}>
                  <Icon name="add" size={16} /> {t("radioLibrary.create")}
                </button>
              </div>
            </div>
            <h4 className="rl-block-title">{t("radioLibrary.tagsTitle")} <span className="rl-nav-count">{tagsList.length}</span></h4>
            {tagsList.length === 0 ? <p className="rl-empty-note">{t("radioLibrary.noTags")}</p> : (
              <div className="rl-cards rl-cards--compact">
                {tagsList.map((tag) => (
                  <div key={tag.id} className="rl-tagcard">
                    <button type="button" className="rl-tagcard-main" onClick={() => applyFilter({ type: "tag", value: tag.name })}>
                      <Icon name="label" size={18} />
                      <span className="rl-pcard-title" title={tag.name}>{tag.name}</span>
                      <span className="rl-nav-count">{tag.track_count}</span>
                    </button>
                    <button type="button" className="rl-tagcard-btn" title={t("radioLibrary.renameTag")} onClick={() => renameTag(tag)}><Icon name="edit" size={15} /></button>
                    <button type="button" className="rl-tagcard-btn" title={t("radioLibrary.deleteTag")} onClick={() => deleteTag(tag)}><Icon name="delete" size={15} /></button>
                  </div>
                ))}
              </div>
            )}
            <h4 className="rl-block-title">{t("radioLibrary.genresTitle")} <span className="rl-nav-count">{genres.length}</span></h4>
            {genres.length === 0 ? <p className="rl-empty-note">{t("radioLibrary.noGenres")}</p> : (
              <div className="rl-cards rl-cards--compact">
                {genres.map((g) => (
                  <div key={g.name} className="rl-tagcard">
                    <button type="button" className="rl-tagcard-main" onClick={() => applyFilter({ type: "genre", value: g.name })}>
                      <Icon name="graphic_eq" size={18} />
                      <span className="rl-pcard-title" title={g.name}>{g.name}</span>
                      <span className="rl-nav-count">{g.count}</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ---------------- Section IMPORTER ---------------- */}
        {section === "import" && (
          <div className="rl-import-section">
            <div className={`upload-zone ${dragActive ? "drag-active" : ""}`}
              onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleFileDrop}
              onClick={openFilesPicker}>
              <input ref={fileInputRef} type="file" accept="audio/*,.zip" multiple
                style={{ display: "none" }} onChange={(e) => startFilesUpload(e.target.files)} />
              <Icon name="cloud_upload" size={44} className="upload-icon" />
              <p style={{ fontSize: "1rem", fontWeight: 800, color: "var(--text-main)", margin: "10px 0 0" }}>
                {t("radioLibrary.importCta")}
              </p>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "2px 0 0" }}>{t("radioLibrary.importHint")}</p>
              <button type="button" onClick={openFolderPicker} className="rl-link-btn">{t("radioLibrary.chooseFolder")}</button>
            </div>
            <h4 className="rl-block-title">{t("radioLibrary.importQueueTitle")}</h4>
            {radioUploads.length === 0 ? (
              <p className="rl-empty-note">{t("radioLibrary.importQueueEmpty")}</p>
            ) : (
              <div className="rl-list">
                {radioUploads.map((u) => (
                  <div key={u.id} className="rl-list-row">
                    <span className="rl-list-cover"><Icon name={u.status === "done" ? "check_circle" : u.status === "error" ? "error" : "cloud_upload"} size={18} /></span>
                    <span className="rl-list-text">
                      <span className="rl-list-title">{u.title}</span>
                      <span className="rl-list-sub">{u.status === "error" ? (u.error ?? t("radioLibrary.importError")) : t(`radioLibrary.importStatus.${u.status}`)}</span>
                    </span>
                    <span className="rl-list-duration">{u.status === "done" ? "100 %" : `${u.progress} %`}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Ferme les popovers en cliquant ailleurs */}
      {bulkMenu && <div className="rl-popover-scrim" onClick={() => setBulkMenu(null)} />}

      {/* ==================== DRAWER : édition d'un morceau ==================== */}
      {selectedTrack && (
        <>
          <div className="detail-drawer-overlay" onClick={() => setSelectedTrack(null)} />
          <div className="detail-drawer">
            <div className="drawer-header">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", maxWidth: "80%" }}>{t("radioLibrary.editTitle")}</h3>
              <button className="close-btn" onClick={() => setSelectedTrack(null)}><Icon name="close" size={20} /></button>
            </div>
            <div className="drawer-body">
              <div style={{ display: "flex", gap: "16px", alignItems: "flex-start", marginBottom: "16px" }}>
                <div style={{ width: "120px", height: "120px", flexShrink: 0, borderRadius: "8px", overflow: "hidden", background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {selectedTrack.has_cover ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={trackCoverUrl(selectedTrack.id)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : <Icon name="music_note" size={36} style={{ opacity: 0.25 }} />}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "8px" }}>{t("radioLibrary.cover")}</div>
                  <input ref={coverInputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => handleCoverSelected(e.target.files)} />
                  <button type="button" className="btn btn-secondary" onClick={() => coverInputRef.current?.click()}><Icon name="image" size={16} /> {t("radioLibrary.changeCover")}</button>
                </div>
              </div>
              <form className="drawer-form" onSubmit={saveMetadata}>
                <div className="form-group"><label className="form-label">{t("radioLibrary.fieldTitle")}</label>
                  <input type="text" className="form-control" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required /></div>
                <div style={{ display: "flex", gap: "12px" }}>
                  <div className="form-group" style={{ flex: 1 }}><label className="form-label">{t("radioLibrary.fieldArtist")}</label>
                    <input type="text" className="form-control" value={form.artist} onChange={(e) => setForm({ ...form, artist: e.target.value })} /></div>
                  <div className="form-group" style={{ flex: 1 }}><label className="form-label">{t("radioLibrary.fieldAlbumArtist")}</label>
                    <input type="text" className="form-control" value={form.album_artist} onChange={(e) => setForm({ ...form, album_artist: e.target.value })} /></div>
                </div>
                <div className="form-group"><label className="form-label">{t("radioLibrary.fieldAlbum")}</label>
                  <input type="text" className="form-control" value={form.album} onChange={(e) => setForm({ ...form, album: e.target.value })} /></div>
                <div style={{ display: "flex", gap: "12px" }}>
                  <div className="form-group" style={{ flex: 1 }}><label className="form-label">{t("radioLibrary.fieldTrackNumber")}</label>
                    <input type="number" className="form-control" value={form.track_number} onChange={(e) => setForm({ ...form, track_number: e.target.value })} /></div>
                  <div className="form-group" style={{ flex: 1 }}><label className="form-label">{t("radioLibrary.fieldDiscNumber")}</label>
                    <input type="number" className="form-control" value={form.disc_number} onChange={(e) => setForm({ ...form, disc_number: e.target.value })} /></div>
                  <div className="form-group" style={{ flex: 1 }}><label className="form-label">{t("radioLibrary.fieldYear")}</label>
                    <input type="number" className="form-control" value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} /></div>
                </div>
                <div className="form-group"><label className="form-label">{t("radioLibrary.fieldGenre")}</label>
                  <input type="text" className="form-control" value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} /></div>

                {/* Tags en chips cliquables */}
                <div className="form-group">
                  <label className="form-label">{t("radioLibrary.fieldTags")}</label>
                  <div className="rl-chips">
                    {Array.from(new Set([...tagsList.map((tg) => tg.name), ...drawerTags])).sort((a, b) => a.localeCompare(b)).map((name) => {
                      const on = drawerTags.includes(name);
                      return (
                        <button key={name} type="button" className={`rl-chip ${on ? "on" : ""}`} onClick={() => toggleDrawerTag(name)}>
                          {on && <Icon name="check" size={13} />} {name}
                        </button>
                      );
                    })}
                  </div>
                  <div className="rl-chip-add">
                    <input type="text" className="form-control" placeholder={t("radioLibrary.addTagPlaceholder")} value={newChip}
                      onChange={(e) => setNewChip(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addChip(); } }} />
                    <button type="button" className="btn btn-secondary" onClick={addChip}><Icon name="add" size={16} /></button>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>{t("radioLibrary.tagsChipsHint")}</span>
                </div>

                <div className="drawer-actions">
                  <button type="submit" className="btn btn-primary" style={{ flex: 1, height: "48px" }} disabled={savingDrawer}>{savingDrawer ? t("radioLibrary.saving") : t("radioLibrary.save")}</button>
                  <button type="button" className="btn btn-danger" style={{ height: "48px" }} onClick={() => setToDelete(selectedTrack)}>{t("radioLibrary.delete")}</button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}

      {/* ==================== DRAWER : édition d'une playlist (façon "Ajouter à la playlist" YouTube Music : liste unique, recherche épinglée, pas de double zone de scroll imbriquée) ==================== */}
      {editingPlaylist && (
        <>
          <div className="detail-drawer-overlay" onClick={() => setEditingPlaylist(null)} />
          <div className="detail-drawer rl-pl-drawer">
            <div className="drawer-header rl-pl-header">
              <input
                type="text" className="rl-pl-name-input"
                value={editingPlaylist.name}
                onChange={(e) => setEditingPlaylist({ ...editingPlaylist, name: e.target.value })}
                onBlur={(e) => renamePlaylist(e.target.value.trim() || editingPlaylist.name)}
                aria-label={t("radioLibrary.playlistNameLabel")}
              />
              <button className="close-btn" onClick={() => setEditingPlaylist(null)}><Icon name="close" size={20} /></button>
            </div>

            <div className="rl-pl-meta">
              <span>{t("radioLibrary.itemsInPlaylist", { count: editingPlaylist.items.length })}</span>
              <span className="rl-pl-meta-dot">·</span>
              <span>{formatDuration(editingPlaylist.total_duration_seconds)}</span>
              <div className="rl-toolbar-spacer" />
              <button type="button" className={`rl-pl-star ${editingPlaylist.is_default ? "on" : ""}`} onClick={toggleDefault} title={editingPlaylist.is_default ? t("radioLibrary.unsetDefault") : t("radioLibrary.setDefault")}>
                <Icon name="star" size={18} filled={editingPlaylist.is_default} />
              </button>
              <button type="button" className="rl-pl-star" onClick={() => setPlaylistToDelete({ id: editingPlaylist.id, name: editingPlaylist.name, is_default: editingPlaylist.is_default, item_count: editingPlaylist.items.length, total_duration_seconds: editingPlaylist.total_duration_seconds, cover_track_id: null })} title={t("radioLibrary.deletePlaylist")}>
                <Icon name="delete" size={18} />
              </button>
            </div>

            <div className="rl-pl-outputs" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", padding: "0 16px 10px" }}>
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }} title={t("radioLibrary.outputDefaultHint")}>
                {t("radioLibrary.outputDefaultLabel")}
              </span>
              {(["radio_cable", "radio_network"] as const).map((radioChannel) => {
                const chosen = outputDefaults?.[radioChannel]?.override_playlist_id === editingPlaylist.id;
                return (
                  <button
                    key={radioChannel}
                    type="button"
                    className={`btn ${chosen ? "btn-primary" : "btn-secondary"}`}
                    style={{ height: "30px", padding: "0 12px", fontSize: "0.78rem" }}
                    aria-pressed={chosen}
                    title={t("radioLibrary.outputDefaultHint")}
                    onClick={() => toggleOutputDefault(radioChannel)}
                  >
                    <Icon name={radioChannel === "radio_cable" ? "cable" : "wifi"} size={14} />
                    {radioChannel === "radio_cable" ? t("radioLibrary.outputCable") : t("radioLibrary.outputNetwork")}
                  </button>
                );
              })}
            </div>

            {/* Recherche épinglée : ajouter un morceau ne fait plus défiler ni
                refermer quoi que ce soit, une seule liste défile en dessous. */}
            <div className="rl-pl-search-bar">
              <Icon name="search" size={18} style={{ opacity: 0.5 }} />
              <SearchBox
                className="rl-pl-search-input"
                placeholder={t("radioLibrary.addTracksSearch")}
                value={addTrackSearch}
                onChange={setAddTrackSearch}
                suggestions={trackSuggestions}
              />
              {addTrackSearch && (
                <button type="button" className="rl-pl-search-clear" onClick={() => setAddTrackSearch("")}><Icon name="close" size={16} /></button>
              )}
            </div>

            <div className="rl-pl-list">
              {addTrackSearch.trim() ? (
                // Mode recherche : toute la bibliothèque, ajout/retrait en un clic.
                addableTracks.length === 0 ? (
                  <p className="rl-empty-note" style={{ padding: "16px" }}>{t("radioLibrary.noResults")}</p>
                ) : addableTracks.map((tr) => {
                  const already = editingPlaylist.items.some((i) => i.track.id === tr.id);
                  const isBusy = addingTrackId === tr.id;
                  return (
                    <div key={tr.id} className="rl-pl-row">
                      <div className="rl-pl-row-thumb">
                        {tr.has_cover ? (
                          // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
                          <img src={trackCoverUrl(tr.id)} alt="" />
                        ) : <Icon name="music_note" size={18} style={{ opacity: 0.3 }} />}
                      </div>
                      <div className="rl-pl-row-text">
                        <span className="rl-pl-row-title">{tr.title}</span>
                        <span className="rl-pl-row-artist">{tr.artist || t("radioLibrary.unknownArtist")}</span>
                      </div>
                      <button
                        type="button"
                        className={`rl-pl-row-action ${already ? "on" : ""}`}
                        disabled={isBusy}
                        onClick={() => (already ? removeFromPlaylist(tr.id) : addToPlaylist(tr.id))}
                        title={already ? t("radioLibrary.remove") : t("radioLibrary.add")}
                      >
                        <Icon name={already ? "check_circle" : "add_circle"} size={26} filled={already} />
                      </button>
                    </div>
                  );
                })
              ) : editingPlaylist.items.length === 0 ? (
                <div className="rl-empty-state" style={{ padding: "32px 16px" }}>
                  <Icon name="queue_music" size={36} style={{ opacity: 0.25, marginBottom: "8px" }} />
                  <p style={{ margin: 0 }}>{t("radioLibrary.emptyPlaylist")}</p>
                </div>
              ) : (
                // Mode aperçu : morceaux déjà dans la playlist, réordonnables.
                editingPlaylist.items.map((item, index) => (
                  <div key={item.id}
                    className={`rl-pl-row ${dragOverIndex === index ? "drag-over" : ""}`}
                    draggable
                    onDragStart={() => { dragIndexRef.current = index; }}
                    onDragOver={(e) => { e.preventDefault(); setDragOverIndex(index); }}
                    onDragLeave={() => setDragOverIndex((cur) => (cur === index ? null : cur))}
                    onDrop={(e) => { e.preventDefault(); handleItemDrop(index); }}
                    onDragEnd={() => { dragIndexRef.current = null; setDragOverIndex(null); }}
                  >
                    <Icon name="drag_indicator" size={18} className="rl-drag-handle" />
                    <div className="rl-pl-row-thumb">
                      {item.track.has_cover ? (
                        // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API
                        <img src={trackCoverUrl(item.track.id)} alt="" />
                      ) : <Icon name="music_note" size={18} style={{ opacity: 0.3 }} />}
                    </div>
                    <div className="rl-pl-row-text">
                      <span className="rl-pl-row-title">{item.track.title}</span>
                      <span className="rl-pl-row-artist">{item.track.artist || t("radioLibrary.unknownArtist")}</span>
                    </div>
                    <span className="rl-pl-row-duration">{formatDuration(item.track.duration_seconds)}</span>
                    <button type="button" className="rl-pl-row-action" title={t("radioLibrary.remove")} onClick={() => removeFromPlaylist(item.track.id)}>
                      <Icon name="close" size={18} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      {/* ==================== MODALES de suppression ==================== */}
      {toDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>{t("radioLibrary.deleteConfirmTitle")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{t("radioLibrary.deleteConfirmText", { title: toDelete.title })}</p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setToDelete(null)}>{t("radioLibrary.cancel")}</button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={confirmDeleteTrack}>{t("radioLibrary.confirmDelete")}</button>
            </div>
          </div>
        </div>
      )}
      {bulkDeleteOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>{t("radioLibrary.bulkDeleteTitle", { count: selected.size })}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{t("radioLibrary.bulkDeleteText")}</p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setBulkDeleteOpen(false)}>{t("radioLibrary.cancel")}</button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={confirmBulkDelete}>{t("radioLibrary.confirmDelete")}</button>
            </div>
          </div>
        </div>
      )}
      {playlistToDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>{t("radioLibrary.deletePlaylist")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{t("radioLibrary.deletePlaylistConfirm", { name: playlistToDelete.name })}</p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setPlaylistToDelete(null)}>{t("radioLibrary.cancel")}</button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={confirmDeletePlaylist}>{t("radioLibrary.confirmDelete")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
