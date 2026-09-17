"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useIsMobile } from "@/lib/useIsMobile";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Language } from "@/lib/i18n";
import Icon from "@/components/Icon";

type TargetType = "video" | "playlist" | "radio_playlist";
type ScheduleTypeValue = "once" | "recurring";
type OverrideActionValue = "cancelled" | "replaced";
type ChannelValue = "cable" | "network" | "radio";

interface VideoSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
}

interface PlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
}

interface RadioPlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
}

interface ScheduleDetail {
  id: number;
  target_type: TargetType;
  target_id: number;
  target_title: string | null;
  target_program: string | null;
  schedule_type: ScheduleTypeValue;
  run_at: string | null;
  days_of_week: number[] | null;
  time_of_day: string | null;
  active: boolean;
  override_count: number;
  // Fenêtre radio (réf. lot L7) : sans objet pour video/playlist.
  end_time: string | null;
  is_24_7: boolean;
}

interface Occurrence {
  schedule_id: number;
  schedule_type: ScheduleTypeValue;
  run_at: string;
  target_type: TargetType;
  target_id: number;
  title: string | null;
  program: string | null;
  // Réf. docs/cahier-des-charges-planning-visuel.md §2 : bloc proportionnel
  // à la durée réelle (vidéo/playlist) ou à la fenêtre choisie (radio, où
  // duration_seconds reste toujours null).
  duration_seconds: number | null;
  thumbnail_path: string | null;
  cover_track_id: number | null;
  end_time: string | null;
  is_24_7: boolean;
  is_override: boolean;
  override_action: OverrideActionValue | null;
  override_id: number | null;
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

function getWeekStart(source: Date): Date {
  const d = new Date(source);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay(); // 0=dimanche .. 6=samedi
  const diff = day === 0 ? -6 : 1 - day; // décale vers le lundi de la semaine
  d.setDate(d.getDate() + diff);
  return d;
}

function addDays(source: Date, days: number): Date {
  const d = new Date(source);
  d.setDate(d.getDate() + days);
  return d;
}

function isSameLocalDay(a: Date, b: Date) {
  return a.toDateString() === b.toDateString();
}

function toDatetimeLocalValue(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function toOccurrenceDateString(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatWeekLabel(weekStart: Date, language: Language) {
  const weekEnd = addDays(weekStart, 6);
  const locale = language === "fr" ? "fr-FR" : "en-US";
  const fmt = (d: Date) => d.toLocaleDateString(locale, { day: "numeric", month: "short" });
  return `${fmt(weekStart)} — ${fmt(weekEnd)}`;
}

function formatOccurrenceTime(iso: string) {
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

function occurrenceKey(o: Occurrence): string {
  return `${o.schedule_id}-${o.run_at}`;
}

function formatDuration(seconds: number | null) {
  if (!seconds) return "";
  const mins = Math.round(seconds / 60);
  return `${mins} min`;
}

// Réf. docs/cahier-des-charges-planning-visuel.md §2-3 : timeline
// proportionnelle à la durée réelle (vidéo/playlist) ou à la fenêtre
// choisie (radio) — mêmes hypothèses que le backend (fenêtres radio jamais
// à cheval sur minuit, cf. schedule.py::_validate_and_normalize).
const MIN_BLOCK_MINUTES = 15;
const MINUTES_PER_DAY = 1440;

function minutesSinceMidnight(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function parseTimeToMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map((n) => parseInt(n, 10));
  return h * 60 + m;
}

interface OccurrenceWindow {
  startMin: number;
  durationMin: number;
  isBackgroundBand: boolean;
}

function getOccurrenceWindow(o: Occurrence): OccurrenceWindow {
  const startMin = minutesSinceMidnight(o.run_at);
  if (o.target_type === "radio_playlist") {
    if (o.is_24_7) {
      return { startMin: 0, durationMin: MINUTES_PER_DAY, isBackgroundBand: true };
    }
    if (o.end_time) {
      const endMin = parseTimeToMinutes(o.end_time);
      const durationMin = endMin > startMin ? endMin - startMin : MIN_BLOCK_MINUTES;
      return { startMin, durationMin, isBackgroundBand: false };
    }
    return { startMin, durationMin: MIN_BLOCK_MINUTES, isBackgroundBand: false };
  }
  const durationMin = o.duration_seconds ? Math.max(o.duration_seconds / 60, MIN_BLOCK_MINUTES) : MIN_BLOCK_MINUTES;
  return { startMin, durationMin, isBackgroundBand: false };
}

function getOccurrenceThumbSrc(o: Occurrence): string | null {
  if (o.target_type === "radio_playlist") {
    return o.cover_track_id != null ? getApiUrl(`/radio/tracks/${o.cover_track_id}/cover`) : null;
  }
  if (!o.thumbnail_path) return null;
  const filename = o.thumbnail_path.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

/**
 * Chevauchement (réf. CDC §5.2/§5.3) : simule le comportement RUNTIME —
 * quand plusieurs occurrences se chevauchent, celle qui démarre le plus tard
 * coupe toujours celle en cours et devient la nouvelle "fenêtre active",
 * quelle que soit la fin initialement prévue de la précédente. Retourne
 * l'ensemble des clés d'occurrences qui coupent quelque chose à leur
 * démarrage (pour l'indicateur visuel), sur une liste déjà triée par heure
 * de début et limitée à un seul jour.
 */
function computeCutsPrevious(dayOccurrences: Occurrence[]): Set<string> {
  const cuts = new Set<string>();
  let activeEndMin = -1;
  for (const o of dayOccurrences) {
    const win = getOccurrenceWindow(o);
    if (win.isBackgroundBand) continue; // l'ambiance de fond ne coupe/n'est jamais coupée
    if (win.startMin < activeEndMin) cuts.add(occurrenceKey(o));
    activeEndMin = win.startMin + win.durationMin;
  }
  return cuts;
}

export default function SchedulePage() {
  const isMobile = useIsMobile();
  const { t, tList, language } = useAppSettings();
  const DAY_LABELS = tList("schedule.dayLabels");
  const DAY_LABELS_FULL = tList("schedule.dayLabelsFull");
  // Réf. docs/cahier-des-charges-planning-visuel.md : l'ancienne grille
  // calendrier (chips de taille uniforme) est remplacée par une timeline
  // proportionnelle à la durée, en granularité Jour ou Semaine — la vue
  // Liste existante n'est pas concernée (§1.2.5).
  const [viewMode, setViewMode] = useState<"day" | "week" | "list">("week");
  // Échelle de la timeline, en pixels par minute (§3 : proportionnel strict
  // + zoom réglable plutôt qu'un plafonnement — un index plutôt qu'un
  // curseur continu, plus simple à piloter aux boutons +/- comme sur
  // mobile, réf. §7).
  const ZOOM_LEVELS = [0.5, 0.8, 1.2, 1.8, 2.6];
  const [zoomIndex, setZoomIndex] = useState(2);
  const pxPerMinute = ZOOM_LEVELS[zoomIndex];
  // Jour affiché en vue Jour (indépendant de weekStart, pour naviguer jour
  // par jour sans perturber la semaine affichée si on repasse en Semaine).
  const [dayViewDate, setDayViewDate] = useState<Date>(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });
  // Planning PAR CANAL de diffusion (réf. mission "un planning pour le Câblé
  // et un pour le Réseau, distincts") : l'onglet actif filtre tout — vue
  // calendrier, vue liste — et toute création se fait sur ce canal. Ouvrable
  // directement sur un canal donné via ?channel= (liens des tableaux de bord).
  const [channel, setChannel] = useState<ChannelValue>(() => {
    if (typeof window === "undefined") return "cable";
    const requested = new URLSearchParams(window.location.search).get("channel");
    return requested === "network" || requested === "radio" ? requested : "cable";
  });

  // La vue Semaine (7 colonnes proportionnelles à la minute) n'est pas
  // exploitable sur un écran de téléphone (réf. CDC planning visuel §7) :
  // bascule sur la vue Jour, seule granularité "timeline" qui garde un sens
  // en une seule colonne — l'utilisateur garde aussi la vue Liste, les deux
  // seules proposées sur mobile (le sélecteur masque Semaine dans ce cas).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise avec le viewport (matchMedia), motif déjà accepté ailleurs (useIsMobile, ClientLayout)
    if (isMobile && viewMode === "week") setViewMode("day");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMobile]);

  // Bibliothèque rapide glisser-déposer (UX3.14) : repliée par défaut sur
  // téléphone (réf. mission "Double Planning", màj mobile) — le
  // glisser-déposer HTML5 ne fonctionne pas au toucher, la garder ouverte
  // n'y mangerait que de la place utile sans rien apporter.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- même motif que viewMode ci-dessus
    if (isMobile) setLibraryOpen(false);
  }, [isMobile]);
  const [weekStart, setWeekStart] = useState<Date>(() => getWeekStart(new Date()));
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [radioPlaylists, setRadioPlaylists] = useState<RadioPlaylistSummary[]>([]);
  const [toast, setToast] = useState<ToastState | null>(null);

  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [replacingKey, setReplacingKey] = useState<string | null>(null);
  const [replaceValue, setReplaceValue] = useState<string>("");

  // Tiroir de création / édition
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingOverrideCount, setEditingOverrideCount] = useState(0);
  const [formTargetType, setFormTargetType] = useState<TargetType>("video");
  const [formTargetId, setFormTargetId] = useState<string>("");
  const [formTargetSearch, setFormTargetSearch] = useState<string>("");
  const [formScheduleType, setFormScheduleType] = useState<ScheduleTypeValue>("once");
  const [formDateTime, setFormDateTime] = useState<string>("");
  const [formDaysOfWeek, setFormDaysOfWeek] = useState<number[]>([]);
  const [formTime, setFormTime] = useState<string>("18:00");
  const [formActive, setFormActive] = useState<boolean>(true);
  // Fenêtre radio (réf. lot L7, D9/A1) : sans effet pour video/playlist.
  const [formEndTime, setFormEndTime] = useState<string>("20:00");
  const [formIs24_7, setFormIs24_7] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState(false);

  // Confirmation de suppression (destructive, réf. UX5.2)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [scheduleToDeleteId, setScheduleToDeleteId] = useState<number | null>(null);

  // Glisser-déposer depuis la bibliothèque rapide (UX3.14)
  const [dragPayload, setDragPayload] = useState<{ type: TargetType; id: number } | null>(null);
  const [dragOverDay, setDragOverDay] = useState<number | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [librarySearch, setLibrarySearch] = useState("");

  const showToast = (message: string, type: ToastState["type"] = "success") => setToast({ message, type });

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  const weekEndExclusive = useMemo(() => addDays(weekStart, 7), [weekStart]);

  const fetchOccurrences = async (start: Date, end: Date) => {
    await Promise.resolve();
    setLoading(true);
    try {
      const params = new URLSearchParams({ start: start.toISOString(), end: end.toISOString(), channel });
      const res = await fetch(getApiUrl(`/schedule/occurrences?${params.toString()}`), { cache: "no-store" });
      if (res.ok) {
        setOccurrences(await res.json());
      } else {
        showToast(t("schedule.fetchError"), "error");
      }
    } catch {
      showToast(t("schedule.fetchNetworkError"), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchOccurrences(weekStart, weekEndExclusive);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekStart, channel]);

  // La vue Jour navigue par jour, mais réutilise le même fetch "semaine"
  // que la vue Semaine (weekStart) plutôt qu'un fetch dédié par jour — plus
  // simple, et navigation instantanée tant qu'on reste dans la même semaine.
  // Ne resynchronise `weekStart` QU'en vue Jour, jamais l'inverse : la vue
  // Semaine garde sa propre navigation indépendante.
  useEffect(() => {
    if (viewMode !== "day") return;
    const dayWeekStart = getWeekStart(dayViewDate);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resynchronise la fenêtre de fetch avec le jour affiché
    if (dayWeekStart.getTime() !== weekStart.getTime()) setWeekStart(dayWeekStart);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dayViewDate, viewMode]);

  useEffect(() => {
    fetch(getApiUrl("/videos?sort_by=imported_at&order=desc"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setVideos)
      .catch(() => setVideos([]));
    fetch(getApiUrl("/playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setPlaylists)
      .catch(() => setPlaylists([]));
    fetch(getApiUrl("/radio/playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setRadioPlaylists)
      .catch(() => setRadioPlaylists([]));
  }, []);

  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);
  const todayRef = new Date();

  const occurrencesByDay = useMemo(
    () =>
      weekDays.map((day) =>
        occurrences
          .filter((o) => isSameLocalDay(new Date(o.run_at), day))
          .sort((a, b) => new Date(a.run_at).getTime() - new Date(b.run_at).getTime())
      ),
    [occurrences, weekDays]
  );

  const sortedOccurrences = useMemo(
    () => [...occurrences].sort((a, b) => new Date(a.run_at).getTime() - new Date(b.run_at).getTime()),
    [occurrences]
  );

  const findVideo = (id: number) => videos.find((v) => v.id === id);
  const findPlaylist = (id: number) => playlists.find((p) => p.id === id);
  const findRadioPlaylist = (id: number) => radioPlaylists.find((p) => p.id === id);

  const targetOptions: { id: number; label: string }[] = useMemo(
    () =>
      formTargetType === "video"
        ? videos.map((v) => ({ id: v.id, label: v.title }))
        : formTargetType === "radio_playlist"
        ? radioPlaylists.map((p) => ({ id: p.id, label: p.name }))
        : playlists.map((p) => ({ id: p.id, label: p.name })),
    [formTargetType, videos, playlists, radioPlaylists]
  );

  const filteredVideos = videos.filter((v) => v.title.toLowerCase().includes(librarySearch.toLowerCase()));
  const filteredPlaylists = playlists.filter((p) => p.name.toLowerCase().includes(librarySearch.toLowerCase()));

  // --------------------------------------------------------------------
  // Navigation semaine
  // --------------------------------------------------------------------
  const goToPreviousWeek = () => setWeekStart((prev) => addDays(prev, -7));
  const goToNextWeek = () => setWeekStart((prev) => addDays(prev, 7));
  const goToToday = () => setWeekStart(getWeekStart(new Date()));

  const goToPreviousDay = () => setDayViewDate((prev) => addDays(prev, -1));
  const goToNextDay = () => setDayViewDate((prev) => addDays(prev, 1));
  const goToTodayDay = () => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    setDayViewDate(d);
  };

  // Bascule Jour/Semaine/Liste (§7) : en passant en vue Jour, aligne le jour
  // affiché sur la semaine déjà chargée si `dayViewDate` s'en est éloigné
  // (ex. resté sur un jour d'une semaine visitée puis quittée pour la vue
  // Semaine, qui a navigué ailleurs) — sinon la vue Jour s'ouvrirait sur un
  // jour hors de portée du fetch courant.
  const switchToDayView = () => {
    if (dayViewDate < weekStart || dayViewDate >= weekEndExclusive) setDayViewDate(weekStart);
    setViewMode("day");
  };

  // --------------------------------------------------------------------
  // Tiroir : création / édition d'une programmation
  // --------------------------------------------------------------------
  const resetForm = () => {
    // Le canal radio n'a qu'un seul type de cible (réf. lot L7) : pas de
    // toggle vidéo/playlist à afficher dans ce cas (cf. JSX du tiroir).
    setFormTargetType(channel === "radio" ? "radio_playlist" : "video");
    setFormTargetId("");
    setFormTargetSearch("");
    setFormScheduleType("once");
    setFormDateTime("");
    setFormDaysOfWeek([]);
    setFormTime("18:00");
    setFormActive(true);
    setFormEndTime("20:00");
    setFormIs24_7(false);
    setEditingOverrideCount(0);
  };

  const openCreateDrawer = (presetDate?: Date, preset?: { type: TargetType; id: number }) => {
    resetForm();
    setEditingId(null);
    if (presetDate) {
      const withTime = new Date(presetDate);
      withTime.setHours(withTime.getHours() + 1, 0, 0, 0);
      setFormDateTime(toDatetimeLocalValue(withTime));
    }
    if (preset) {
      setFormTargetType(preset.type);
      setFormTargetId(String(preset.id));
    }
    setDrawerOpen(true);
  };

  const openEditDrawer = async (scheduleId: number) => {
    try {
      const res = await fetch(getApiUrl(`/schedule/${scheduleId}`), { cache: "no-store" });
      if (!res.ok) {
        showToast(t("schedule.loadScheduleError"), "error");
        return;
      }
      const data: ScheduleDetail = await res.json();
      setEditingId(data.id);
      setFormTargetType(data.target_type);
      setFormTargetId(String(data.target_id));
      setFormTargetSearch("");
      setFormScheduleType(data.schedule_type);
      setFormDateTime(data.run_at ? toDatetimeLocalValue(new Date(data.run_at)) : "");
      setFormDaysOfWeek(data.days_of_week ?? []);
      setFormTime(data.time_of_day ?? "18:00");
      setFormActive(data.active);
      setFormEndTime(data.end_time ?? "20:00");
      setFormIs24_7(data.is_24_7 ?? false);
      setEditingOverrideCount(data.override_count);
      setDrawerOpen(true);
    } catch {
      showToast(t("schedule.networkError"), "error");
    }
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditingId(null);
  };

  const toggleFormDay = (day: number) => {
    setFormDaysOfWeek((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort((a, b) => a - b)));
  };

  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTargetId) {
      showToast(t("schedule.chooseTargetWarning"), "warning");
      return;
    }
    if (formScheduleType === "once" && !formDateTime) {
      showToast(t("schedule.chooseDateTimeWarning"), "warning");
      return;
    }
    if (formScheduleType === "recurring" && formDaysOfWeek.length === 0) {
      showToast(t("schedule.chooseDayWarning"), "warning");
      return;
    }

    const payload: Record<string, unknown> = {
      target_type: formTargetType,
      target_id: Number(formTargetId),
      schedule_type: formScheduleType,
      active: formActive,
      // Une programmation appartient au canal de l'onglet actif (réf.
      // mission "un planning pour le Câblé et un pour le Réseau").
      channel,
    };
    if (formScheduleType === "once") {
      payload.run_at = new Date(formDateTime).toISOString();
    } else {
      payload.days_of_week = formDaysOfWeek;
      payload.time_of_day = formTime;
      // Fenêtre radio (réf. lot L7, D9/A1) : sans effet côté backend pour
      // video/playlist, mais inutile de les envoyer hors de ce cas.
      if (formTargetType === "radio_playlist") {
        payload.is_24_7 = formIs24_7;
        if (!formIs24_7) payload.end_time = formEndTime;
      }
    }

    setIsSaving(true);
    try {
      const url = editingId ? getApiUrl(`/schedule/${editingId}`) : getApiUrl("/schedule");
      const method = editingId ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        showToast(editingId ? t("schedule.updatedToast") : t("schedule.createdToast"));
        closeDrawer();
        fetchOccurrences(weekStart, weekEndExclusive);
      } else {
        const data = await res.json().catch(() => null);
        showToast(data?.detail || t("schedule.saveError"), "error");
      }
    } catch {
      showToast(t("schedule.saveNetworkError"), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const triggerDeleteSchedule = () => {
    if (!editingId) return;
    setScheduleToDeleteId(editingId);
    setShowDeleteConfirm(true);
  };

  const confirmDeleteSchedule = async () => {
    if (!scheduleToDeleteId) return;
    try {
      const res = await fetch(getApiUrl(`/schedule/${scheduleToDeleteId}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("schedule.deletedToast"));
        closeDrawer();
        fetchOccurrences(weekStart, weekEndExclusive);
      } else {
        showToast(t("schedule.deleteError"), "error");
      }
    } catch {
      showToast(t("schedule.networkError"), "error");
    } finally {
      setShowDeleteConfirm(false);
      setScheduleToDeleteId(null);
    }
  };

  // --------------------------------------------------------------------
  // Overrides — actions rapides sur une occurrence (UX3.15)
  // --------------------------------------------------------------------
  const handleCancelOccurrence = async (o: Occurrence) => {
    try {
      const res = await fetch(getApiUrl(`/schedule/${o.schedule_id}/overrides`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ occurrence_date: toOccurrenceDateString(o.run_at), action: "cancelled" }),
      });
      if (res.ok) {
        showToast(t("schedule.cancelledToast"));
        setExpandedKey(null);
        fetchOccurrences(weekStart, weekEndExclusive);
      } else {
        showToast(t("schedule.cancelError"), "error");
      }
    } catch {
      showToast(t("schedule.networkError"), "error");
    }
  };

  const handleRestoreOccurrence = async (o: Occurrence) => {
    if (!o.override_id) return;
    try {
      const res = await fetch(getApiUrl(`/schedule/${o.schedule_id}/overrides/${o.override_id}`), {
        method: "DELETE",
      });
      if (res.ok) {
        showToast(t("schedule.restoredToast"));
        setExpandedKey(null);
        fetchOccurrences(weekStart, weekEndExclusive);
      } else {
        showToast(t("schedule.restoreError"), "error");
      }
    } catch {
      showToast(t("schedule.networkError"), "error");
    }
  };

  const handleConfirmReplace = async (o: Occurrence) => {
    if (!replaceValue) return;
    const [type, idStr] = replaceValue.split(":");
    try {
      const res = await fetch(getApiUrl(`/schedule/${o.schedule_id}/overrides`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          occurrence_date: toOccurrenceDateString(o.run_at),
          action: "replaced",
          replacement_target_type: type,
          replacement_target_id: Number(idStr),
        }),
      });
      if (res.ok) {
        showToast(t("schedule.replacedToast"));
        setReplacingKey(null);
        setExpandedKey(null);
        fetchOccurrences(weekStart, weekEndExclusive);
      } else {
        showToast(t("schedule.replaceError"), "error");
      }
    } catch {
      showToast(t("schedule.networkError"), "error");
    }
  };

  // --------------------------------------------------------------------
  // Glisser-déposer bibliothèque -> jour (UX3.14)
  // --------------------------------------------------------------------
  const handleDropOnDay = (dayIndex: number) => {
    setDragOverDay(null);
    if (!dragPayload) return;
    openCreateDrawer(weekDays[dayIndex], dragPayload);
    setDragPayload(null);
  };

  // Couleur du thème plutôt que du programme du cours (réf. correctif
  // "couleurs hardcodées associées à un cours" — le thème prime désormais).
  const getProgramAccent = () => "var(--accent-primary)";

  // Panneau d'actions rapides (édition/annulation/rétablissement/remplacement
  // d'une occurrence, UX3.15) — factorisé pour être partagé entre la chip de
  // la vue Liste et le bloc proportionnel des vues Jour/Semaine plutôt que
  // dupliqué (même comportement, juste un conteneur visuel différent).
  const renderOccurrenceActions = (o: Occurrence, key: string) => {
    const isCancelled = o.override_action === "cancelled";
    const isReplaced = o.override_action === "replaced";
    const isRecurring = o.schedule_type === "recurring";
    return (
      <div className="schedule-occurrence-actions" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="btn btn-secondary" onClick={() => openEditDrawer(o.schedule_id)}>
          {t("schedule.editSeries")}
        </button>
        {isRecurring && !isCancelled && !isReplaced && (
          <button type="button" className="btn btn-secondary" onClick={() => handleCancelOccurrence(o)}>
            {t("schedule.cancelOccurrence")}
          </button>
        )}
        {isRecurring && (isCancelled || isReplaced) && (
          <button type="button" className="btn btn-secondary" onClick={() => handleRestoreOccurrence(o)}>
            {t("schedule.restoreOccurrence")}
          </button>
        )}
        {isRecurring && !isCancelled && (
          <>
            {replacingKey === key ? (
              <>
                <select
                  className="filter-select"
                  value={replaceValue}
                  onChange={(e) => setReplaceValue(e.target.value)}
                  style={{ width: "100%", height: "26px", fontSize: "0.7rem" }}
                >
                  <option value="">{t("schedule.replaceWith")}</option>
                  {o.target_type === "radio_playlist" ? (
                    <optgroup label={t("schedule.radioPlaylistsGroup")}>
                      {radioPlaylists.map((p) => (
                        <option key={`rp-${p.id}`} value={`radio_playlist:${p.id}`}>
                          {p.name}
                        </option>
                      ))}
                    </optgroup>
                  ) : (
                    <>
                      <optgroup label={t("schedule.videosGroup")}>
                        {videos.map((v) => (
                          <option key={`v-${v.id}`} value={`video:${v.id}`}>
                            {v.title}
                          </option>
                        ))}
                      </optgroup>
                      <optgroup label={t("schedule.playlistsGroup")}>
                        {playlists.map((p) => (
                          <option key={`p-${p.id}`} value={`playlist:${p.id}`}>
                            {p.name}
                          </option>
                        ))}
                      </optgroup>
                    </>
                  )}
                </select>
                <button type="button" className="btn btn-primary" onClick={() => handleConfirmReplace(o)}>
                  {t("schedule.confirmReplace")}
                </button>
              </>
            ) : (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setReplaceValue("");
                  setReplacingKey(key);
                }}
              >
                {t("schedule.replaceOccurrence")}
              </button>
            )}
          </>
        )}
      </div>
    );
  };

  const renderOccurrenceChip = (o: Occurrence, compact: boolean) => {
    const key = occurrenceKey(o);
    const isExpanded = expandedKey === key;
    const isCancelled = o.override_action === "cancelled";
    const isReplaced = o.override_action === "replaced";

    return (
      <div
        key={key}
        className={`schedule-occurrence-chip ${isCancelled ? "cancelled" : ""}`}
        style={{ borderLeftColor: getProgramAccent() }}
        onClick={(e) => {
          e.stopPropagation();
          setReplacingKey(null);
          setExpandedKey(isExpanded ? null : key);
        }}
      >
        <div className="schedule-occurrence-time">
          {formatOccurrenceTime(o.run_at)}
          {compact && ` · ${DAY_LABELS_FULL[(new Date(o.run_at).getDay() + 6) % 7]}`}
        </div>
        <div className="schedule-occurrence-title">{o.title ?? t("schedule.targetNotFound")}</div>
        {isReplaced && <span className="schedule-occurrence-badge">{t("schedule.replacedBadge")}</span>}
        {isCancelled && <span className="schedule-occurrence-badge">{t("schedule.cancelledBadge")}</span>}

        {isExpanded && renderOccurrenceActions(o, key)}
      </div>
    );
  };

  // Bloc proportionnel à la durée (vues Jour/Semaine, réf. CDC §2-3) :
  // positionné en absolu dans sa colonne via `style` (top/height calculés
  // par l'appelant selon pxPerMinute), miniature par type de média,
  // indicateur de chevauchement au tap (§5.2, pas de survol au tactile).
  const renderTimelineBlock = (o: Occurrence, style: React.CSSProperties, cutsPrevious: boolean) => {
    const key = occurrenceKey(o);
    const isExpanded = expandedKey === key;
    const isCancelled = o.override_action === "cancelled";
    const isReplaced = o.override_action === "replaced";
    const thumbSrc = getOccurrenceThumbSrc(o);
    const win = getOccurrenceWindow(o);
    const durationLabel =
      o.target_type === "radio_playlist"
        ? o.end_time
          ? `${formatOccurrenceTime(o.run_at)}–${o.end_time}`
          : formatOccurrenceTime(o.run_at)
        : `${formatOccurrenceTime(o.run_at)} · ${formatDuration(o.duration_seconds)}`;

    return (
      <div
        key={key}
        className={`schedule-timeline-block ${isCancelled ? "cancelled" : ""} ${cutsPrevious ? "cuts-previous" : ""}`}
        style={style}
        title={cutsPrevious ? t("schedule.overlapTooltip") : undefined}
        onClick={(e) => {
          e.stopPropagation();
          setReplacingKey(null);
          setExpandedKey(isExpanded ? null : key);
        }}
      >
        <div className="schedule-timeline-block-thumb">
          {thumbSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={thumbSrc} alt="" />
          ) : (
            <Icon
              name={o.target_type === "radio_playlist" ? "graphic_eq" : o.target_type === "playlist" ? "playlist_play" : "movie"}
              size={18}
              style={{ opacity: 0.35 }}
            />
          )}
          {cutsPrevious && (
            <span className="schedule-timeline-cut-badge">
              <Icon name="content_cut" size={11} />
            </span>
          )}
        </div>
        <div className="schedule-timeline-block-body">
          <div className="schedule-timeline-block-title">{o.title ?? t("schedule.targetNotFound")}</div>
          <div className="schedule-timeline-block-time">{durationLabel}</div>
          {isReplaced && <span className="schedule-occurrence-badge">{t("schedule.replacedBadge")}</span>}
          {isCancelled && <span className="schedule-occurrence-badge">{t("schedule.cancelledBadge")}</span>}
        </div>
        {isExpanded && !win.isBackgroundBand && renderOccurrenceActions(o, key)}
      </div>
    );
  };

  // Bande de fond "ambiance permanente 24/7" (réf. CDC §2.4) : un vrai calque
  // de fond sur toute la hauteur de la journée (z-index sous les blocs
  // normaux), pas un bloc de plus — un bloc normal qui se trouve par-dessus
  // le masque naturellement à cet endroit (empilement standard), sans avoir
  // à calculer les créneaux libres explicitement.
  const renderBackgroundBand = (o: Occurrence) => (
    <div
      key={occurrenceKey(o)}
      className="schedule-timeline-band-247"
      title={o.title ?? t("schedule.permanentAmbianceLabel")}
      style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0 }}
    >
      <div className="schedule-timeline-band-247-label">
        <Icon name="graphic_eq" size={12} />
        <span>{o.title ?? t("schedule.permanentAmbianceLabel")}</span>
      </div>
    </div>
  );

  const HOUR_HEIGHT = 60 * pxPerMinute;

  const renderTimelineColumn = (day: Date, dayIndex: number, dayOccurrences: Occurrence[]) => {
    const isToday = isSameLocalDay(day, todayRef);
    const bands = dayOccurrences.filter((o) => getOccurrenceWindow(o).isBackgroundBand);
    const timedOccurrences = dayOccurrences.filter((o) => !getOccurrenceWindow(o).isBackgroundBand);
    const cutsPreviousKeys = computeCutsPrevious(timedOccurrences);

    return (
      <div
        key={dayIndex}
        className={`schedule-timeline-column ${isToday ? "today" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOverDay(dayIndex);
        }}
        onDragLeave={() => setDragOverDay(null)}
        onDrop={() => handleDropOnDay(dayIndex)}
      >
        <div
          className={`schedule-timeline-track ${dragOverDay === dayIndex ? "drag-over" : ""}`}
          style={{ height: MINUTES_PER_DAY * pxPerMinute }}
          onClick={() => openCreateDrawer(day)}
        >
          {bands.map(renderBackgroundBand)}
          {Array.from({ length: 24 }, (_, hour) => (
            <div key={hour} className="schedule-timeline-hour-row" style={{ height: HOUR_HEIGHT }}>
              <span className="schedule-timeline-hour-label">{`${hour.toString().padStart(2, "0")}:00`}</span>
            </div>
          ))}
          {timedOccurrences.map((o) => {
            const win = getOccurrenceWindow(o);
            return renderTimelineBlock(
              o,
              {
                position: "absolute",
                top: win.startMin * pxPerMinute,
                height: win.durationMin * pxPerMinute,
                left: 4,
                right: 4,
                zIndex: 1,
              },
              cutsPreviousKeys.has(occurrenceKey(o))
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="schedule-page">
      {toast && (
        <div className={`toast ${toast.type}`}>
          <span>{toast.message}</span>
        </div>
      )}

      <div className="schedule-toolbar">
        {/* Onglets de canal (réf. mission "un planning pour le Câblé et un
            pour le Réseau, distincts") : tout ce qui suit — calendrier,
            liste, créations — ne concerne que le canal sélectionné. */}
        <div className="view-toggle">
          <button
            className={`view-btn olc-press ${channel === "cable" ? "active" : ""}`}
            onClick={() => setChannel("cable")}
            title={t("schedule.channelCableTitle")}
            style={{ display: "flex", alignItems: "center", gap: "6px", padding: "0 12px" }}
          >
            <Icon name="cable" size={16} />
            {t("schedule.channelTabCable")}
          </button>
          <button
            className={`view-btn olc-press ${channel === "network" ? "active" : ""}`}
            onClick={() => setChannel("network")}
            title={t("schedule.channelNetworkTitle")}
            style={{ display: "flex", alignItems: "center", gap: "6px", padding: "0 12px" }}
          >
            <Icon name="wifi" size={16} />
            {t("schedule.channelTabNetwork")}
          </button>
          <button
            className={`view-btn olc-press ${channel === "radio" ? "active" : ""}`}
            onClick={() => setChannel("radio")}
            title={t("schedule.channelRadioTitle")}
            style={{ display: "flex", alignItems: "center", gap: "6px", padding: "0 12px" }}
          >
            <Icon name="graphic_eq" size={16} />
            {t("schedule.channelTabRadio")}
          </button>
        </div>
        {viewMode === "day" ? (
          <div className="week-nav">
            <button className="btn btn-secondary" onClick={goToPreviousDay} title={t("schedule.previousDayTitle")}>
              <Icon name="chevron_left" size={16} />
            </button>
            <button className="btn btn-secondary" onClick={goToTodayDay}>
              {t("schedule.today")}
            </button>
            <button className="btn btn-secondary" onClick={goToNextDay} title={t("schedule.nextDayTitle")}>
              <Icon name="chevron_right" size={16} />
            </button>
            <span className="week-nav-label">
              {DAY_LABELS_FULL[(dayViewDate.getDay() + 6) % 7]} {dayViewDate.toLocaleDateString(language === "fr" ? "fr-FR" : "en-US", { day: "numeric", month: "short" })}
            </span>
          </div>
        ) : viewMode === "week" ? (
          <div className="week-nav">
            <button className="btn btn-secondary" onClick={goToPreviousWeek} title={t("schedule.previousWeekTitle")}>
              <Icon name="chevron_left" size={16} />
              {t("schedule.previousWeekShort")}
            </button>
            <button className="btn btn-secondary" onClick={goToToday}>
              {t("schedule.today")}
            </button>
            <button className="btn btn-secondary" onClick={goToNextWeek} title={t("schedule.nextWeekTitle")}>
              {t("schedule.nextWeekShort")}
              <Icon name="chevron_right" size={16} />
            </button>
            <span className="week-nav-label">{formatWeekLabel(weekStart, language)}</span>
          </div>
        ) : (
          <div className="week-nav" />
        )}

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          {viewMode !== "list" && (
            <div className="view-toggle" title={t("schedule.zoomTitle")}>
              <button
                type="button"
                className="view-btn olc-press"
                onClick={() => setZoomIndex((z) => Math.max(0, z - 1))}
                disabled={zoomIndex === 0}
                title={t("schedule.zoomOutTitle")}
              >
                <Icon name="zoom_out" size={16} />
              </button>
              <button
                type="button"
                className="view-btn olc-press"
                onClick={() => setZoomIndex((z) => Math.min(ZOOM_LEVELS.length - 1, z + 1))}
                disabled={zoomIndex === ZOOM_LEVELS.length - 1}
                title={t("schedule.zoomInTitle")}
              >
                <Icon name="zoom_in" size={16} />
              </button>
            </div>
          )}
          <div className="view-toggle">
            <button
              className={`view-btn olc-press ${viewMode === "day" ? "active" : ""}`}
              onClick={switchToDayView}
              title={t("schedule.dayView")}
            >
              <Icon name="view_day" size={18} />
            </button>
            {/* Vue Semaine masquée sur mobile (réf. CDC planning visuel §7) :
                7 colonnes proportionnelles à la minute illisibles à cette
                largeur — Jour + Liste couvrent le besoin sans ce compromis. */}
            {!isMobile && (
              <button
                className={`view-btn olc-press ${viewMode === "week" ? "active" : ""}`}
                onClick={() => setViewMode("week")}
                title={t("schedule.weekView")}
              >
                <Icon name="calendar_view_week" size={18} />
              </button>
            )}
            <button
              className={`view-btn olc-press ${viewMode === "list" ? "active" : ""}`}
              onClick={() => setViewMode("list")}
              title={t("schedule.listView")}
            >
              <Icon name="view_list" size={18} />
            </button>
          </div>
          <button className="btn btn-primary" onClick={() => openCreateDrawer()}>
            <Icon name="add" size={18} />
            {t("schedule.newSchedule")}
          </button>
        </div>
      </div>

      <div className="schedule-body" style={{ flexDirection: isMobile ? "column" : "row", gap: "20px" }}>
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>
          {loading ? (
            <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              {t("schedule.loadingSchedule")}
            </div>
          ) : viewMode === "week" ? (
            <div className="schedule-timeline-scroll">
              <div className="schedule-timeline-week-grid">
                {weekDays.map((day, index) => (
                  <div key={index} className="schedule-timeline-week-col">
                    <div className="schedule-day-header">
                      <span className="schedule-day-header-name">{DAY_LABELS_FULL[index]}</span>
                      <span className="schedule-day-header-date">{day.getDate()}</span>
                    </div>
                    {renderTimelineColumn(day, index, occurrencesByDay[index])}
                  </div>
                ))}
              </div>
            </div>
          ) : viewMode === "day" ? (
            <div className="schedule-timeline-scroll">
              <div className="schedule-timeline-day-single">
                {renderTimelineColumn(
                  dayViewDate,
                  weekDays.findIndex((d) => isSameLocalDay(d, dayViewDate)),
                  occurrencesByDay[weekDays.findIndex((d) => isSameLocalDay(d, dayViewDate))] ?? []
                )}
              </div>
            </div>
          ) : (
            <div className="schedule-list-scroll">
              {sortedOccurrences.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                  {t("schedule.noScheduleThisWeek")}
                </div>
              ) : (
                weekDays.map((day, index) =>
                  occurrencesByDay[index].length === 0 ? null : (
                    <div key={index} className="schedule-list-day-group">
                      <div className="schedule-list-day-label">
                        {DAY_LABELS_FULL[index]} {day.getDate()}
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {occurrencesByDay[index].map((o) => renderOccurrenceChip(o, true))}
                      </div>
                    </div>
                  )
                )
              )}
            </div>
          )}
        </div>

        {/* Bibliothèque rapide (glisser-déposer sur un jour, UX3.14) : le
            glisser-déposer HTML5 n'existe pas au toucher, ce panneau reste
            surtout un raccourci de recherche sur téléphone — d'où la largeur
            pleine plutôt que la colonne fixe du PC. Sans objet sur le canal
            radio (réf. lot L7) : un seul type de cible (playlist radio), pas
            de bibliothèque vidéo/playlist à glisser-déposer ici. */}
        {libraryOpen && channel !== "radio" && (
          <div className="library-picker" style={{ width: isMobile ? "100%" : "260px", height: "auto", flexShrink: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="form-label" style={{ margin: 0 }}>
                {t("schedule.quickLibrary")}
              </span>
              <button className="close-btn" onClick={() => setLibraryOpen(false)} title={t("schedule.hide")}>
                <Icon name="close" size={16} />
              </button>
            </div>
            <input
              type="text"
              className="form-control"
              placeholder={t("schedule.searchPlaceholder")}
              value={librarySearch}
              onChange={(e) => setLibrarySearch(e.target.value)}
              style={{ height: "32px", fontSize: "0.8rem" }}
            />
            <p style={{ fontSize: "0.7rem", color: "var(--text-dim)", margin: 0 }}>
              {t("schedule.dragHint")}
            </p>
            <div className="library-picker-list">
              {filteredVideos.map((v) => (
                <div
                  key={`v-${v.id}`}
                  className="library-picker-item"
                  draggable
                  onDragStart={() => setDragPayload({ type: "video", id: v.id })}
                >
                  <span style={{ fontWeight: 700, fontSize: "0.8rem", color: "var(--text-main)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {v.title}
                  </span>
                  <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{formatDuration(v.duration_seconds)}</span>
                </div>
              ))}
              {filteredPlaylists.map((p) => (
                <div
                  key={`p-${p.id}`}
                  className="library-picker-item"
                  draggable
                  onDragStart={() => setDragPayload({ type: "playlist", id: p.id })}
                >
                  <span style={{ fontWeight: 700, fontSize: "0.8rem", color: "var(--text-main)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: "4px" }}>
                    <Icon name="playlist_play" size={14} />
                    {p.name}
                  </span>
                  <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{t("schedule.coursesCount", { count: p.item_count })}</span>
                </div>
              ))}
              {filteredVideos.length === 0 && filteredPlaylists.length === 0 && (
                <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem", padding: "12px" }}>
                  {t("schedule.noResults")}
                </div>
              )}
            </div>
          </div>
        )}
        {!libraryOpen && channel !== "radio" && (
          <button
            className="btn btn-secondary"
            style={isMobile ? { width: "100%" } : { writingMode: "vertical-rl", height: "100%" }}
            onClick={() => setLibraryOpen(true)}
          >
            {t("schedule.libraryCollapsed")}
          </button>
        )}
      </div>

      {/* Tiroir de création / édition */}
      {drawerOpen && (
        <>
          <div className="detail-drawer-overlay" onClick={closeDrawer} />
          <div className="detail-drawer">
            <div className="drawer-header">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>
                {editingId ? t("schedule.editScheduleTitle") : t("schedule.newScheduleTitle")}
              </h3>
              <button className="close-btn" onClick={closeDrawer}>
                <Icon name="close" size={20} />
              </button>
            </div>
            <form onSubmit={handleSaveSchedule} className="drawer-body drawer-form">
              <div className="form-group">
                <label className="form-label">
                  {channel === "radio" ? t("schedule.radioPlaylistLabel") : t("schedule.targetLabel")}
                </label>
                {/* Le canal radio n'a qu'un seul type de cible (playlist
                    radio, réf. lot L7) : pas de toggle à afficher, contrairement
                    au câblé/réseau qui choisissent entre vidéo et playlist. */}
                {channel !== "radio" && (
                  <div className="speed-group" style={{ width: "100%" }}>
                    <button
                      type="button"
                      className={`speed-btn ${formTargetType === "video" ? "active" : ""}`}
                      style={{ flex: 1 }}
                      onClick={() => {
                        setFormTargetType("video");
                        setFormTargetId("");
                      }}
                    >
                      {t("schedule.videoOption")}
                    </button>
                    <button
                      type="button"
                      className={`speed-btn ${formTargetType === "playlist" ? "active" : ""}`}
                      style={{ flex: 1 }}
                      onClick={() => {
                        setFormTargetType("playlist");
                        setFormTargetId("");
                      }}
                    >
                      {t("schedule.playlistOption")}
                    </button>
                  </div>
                )}
              </div>

              <div className="form-group">
                <input
                  type="text"
                  className="form-control"
                  placeholder={t("schedule.searchPlaceholder")}
                  value={formTargetSearch}
                  onChange={(e) => setFormTargetSearch(e.target.value)}
                />
                <div className="library-picker-list" style={{ maxHeight: "160px" }}>
                  {targetOptions
                    .filter((opt) => opt.label.toLowerCase().includes(formTargetSearch.toLowerCase()))
                    .map((opt) => {
                      const selected = String(opt.id) === formTargetId;
                      return (
                        <div
                          key={opt.id}
                          className="library-picker-item"
                          style={{
                            cursor: "pointer",
                            borderColor: selected ? "var(--accent-primary)" : undefined,
                            background: selected ? "color-mix(in srgb, var(--accent-primary) 8%, transparent)" : undefined,
                          }}
                          onClick={() => setFormTargetId(String(opt.id))}
                        >
                          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-main)" }}>{opt.label}</span>
                        </div>
                      );
                    })}
                </div>
                {formTargetId && (
                  <span style={{ fontSize: "0.75rem", color: "var(--accent-success)" }}>
                    {t("schedule.selectedLabel")}{" "}
                    {formTargetType === "video"
                      ? findVideo(Number(formTargetId))?.title
                      : formTargetType === "radio_playlist"
                      ? findRadioPlaylist(Number(formTargetId))?.name
                      : findPlaylist(Number(formTargetId))?.name}
                  </span>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">{t("schedule.scheduleTypeLabel")}</label>
                <div className="speed-group" style={{ width: "100%" }}>
                  <button
                    type="button"
                    className={`speed-btn ${formScheduleType === "once" ? "active" : ""}`}
                    style={{ flex: 1 }}
                    onClick={() => setFormScheduleType("once")}
                  >
                    {t("schedule.onceOption")}
                  </button>
                  <button
                    type="button"
                    className={`speed-btn ${formScheduleType === "recurring" ? "active" : ""}`}
                    style={{ flex: 1 }}
                    onClick={() => setFormScheduleType("recurring")}
                  >
                    {t("schedule.recurringOption")}
                  </button>
                </div>
              </div>

              {formScheduleType === "once" ? (
                <div className="form-group">
                  <label className="form-label">{t("schedule.dateTimeLabel")}</label>
                  <input
                    type="datetime-local"
                    className="form-control"
                    value={formDateTime}
                    onChange={(e) => setFormDateTime(e.target.value)}
                  />
                </div>
              ) : (
                <>
                  <div className="form-group">
                    <label className="form-label">{t("schedule.daysOfWeekLabel")}</label>
                    <div className="speed-group" style={{ width: "100%" }}>
                      {DAY_LABELS.map((label, idx) => (
                        <button
                          key={idx}
                          type="button"
                          className={`speed-btn ${formDaysOfWeek.includes(idx) ? "active" : ""}`}
                          style={{ flex: 1 }}
                          onClick={() => toggleFormDay(idx)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">{t("schedule.hourLabel")}</label>
                    <input
                      type="time"
                      className="form-control"
                      value={formTime}
                      onChange={(e) => setFormTime(e.target.value)}
                    />
                  </div>

                  {/* Fenêtre radio (réf. lot L7, D9/A1) : sans objet pour
                      vidéo/playlist. 24/7 = la playlist remplace le défaut
                      indéfiniment (pas de retour auto) ; sinon une heure de
                      fin déclenche le retour à l'ambiance par défaut. */}
                  {formTargetType === "radio_playlist" && (
                    <>
                      <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "10px" }}>
                        <input
                          type="checkbox"
                          checked={formIs24_7}
                          onChange={(e) => setFormIs24_7(e.target.checked)}
                          style={{ width: "18px", height: "18px" }}
                        />
                        <label className="form-label" style={{ margin: 0 }}>
                          {t("schedule.is247Label")}
                        </label>
                      </div>
                      {!formIs24_7 && (
                        <div className="form-group">
                          <label className="form-label">{t("schedule.endTimeLabel")}</label>
                          <input
                            type="time"
                            className="form-control"
                            value={formEndTime}
                            onChange={(e) => setFormEndTime(e.target.value)}
                          />
                          <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: "4px 0 0" }}>
                            {t("schedule.endTimeHint")}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}

              <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "10px" }}>
                <input
                  type="checkbox"
                  checked={formActive}
                  onChange={(e) => setFormActive(e.target.checked)}
                  style={{ width: "18px", height: "18px" }}
                />
                <label className="form-label" style={{ margin: 0 }}>
                  {t("schedule.activeLabel")}
                </label>
              </div>

              {editingId && editingOverrideCount > 0 && (
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  {t("schedule.overrideCountHint", { count: editingOverrideCount })}
                </p>
              )}

              <div className="drawer-actions">
                <button type="submit" className="btn btn-primary" disabled={isSaving}>
                  {isSaving ? t("common.saving") : t("common.save")}
                </button>
                <button type="button" className="btn btn-secondary" onClick={closeDrawer} disabled={isSaving}>
                  {t("common.cancel")}
                </button>
                {editingId && (
                  <button type="button" className="btn btn-danger" onClick={triggerDeleteSchedule} disabled={isSaving}>
                    {t("schedule.deleteScheduleBtn")}
                  </button>
                )}
              </div>
            </form>
          </div>
        </>
      )}

      {/* Confirmation de suppression (destructive, réf. UX5.2) */}
      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", margin: "0 0 12px" }}>{t("schedule.deleteScheduleTitle")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: "0 0 20px", lineHeight: 1.5 }}>
              {t("schedule.deleteScheduleConfirm")}
            </p>
            <div className="modal-actions">
              <button className="btn btn-danger" onClick={confirmDeleteSchedule}>
                {t("common.delete")}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setScheduleToDeleteId(null);
                }}
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
