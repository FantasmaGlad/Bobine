"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useIsMobile } from "@/lib/useIsMobile";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Language } from "@/lib/i18n";
import Icon from "@/components/Icon";
import ScrollNav from "@/components/ScrollNav";
import { isRadioLane, parseScheduleChannel, type ScheduleChannel } from "@/lib/scheduleChannels";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SearchBox from "@/components/SearchBox";
import Highlight from "@/components/Highlight";
import { matchesQuery } from "@/lib/searchText";

type TargetType = "video" | "playlist" | "radio_playlist";
type ScheduleTypeValue = "once" | "recurring";
type OverrideActionValue = "cancelled" | "replaced";
type ChannelValue = ScheduleChannel;

interface VideoSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  thumbnail_path: string | null;
}

interface PlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
  thumbnail_path: string | null;
}

interface RadioPlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
  /** Morceau dont la pochette illustre la playlist (1er morceau ayant une pochette). */
  cover_track_id?: number | null;
  is_default?: boolean;
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
  // Fenêtre radio : sans objet pour video/playlist.
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
  // Bloc proportionnel
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

function minutesToHHMM(minutes: number): string {
  const h = Math.floor(minutes / 60) % 24;
  const m = Math.round(minutes % 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

// Timeline
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

function getThumbnailSrc(thumbnailPath: string | null): string | null {
  if (!thumbnailPath) return null;
  const filename = thumbnailPath.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

function getOccurrenceThumbSrc(o: Occurrence): string | null {
  if (o.target_type === "radio_playlist") {
    return o.cover_track_id != null ? getApiUrl(`/radio/tracks/${o.cover_track_id}/cover`) : null;
  }
  return getThumbnailSrc(o.thumbnail_path);
}

/**
 * Chevauchement : simule le comportement RUNTIME —
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
  // l'ancienne grille
  // calendrier (chips de taille uniforme) est remplacée par une timeline
  // proportionnelle à la durée, en granularité Jour ou Semaine — la vue
  // Liste existante n'est pas concernée.
  const [viewMode, setViewMode] = useState<"day" | "week" | "list">("week");
  // Échelle de la timeline, en pixels par minute (proportionnel strict
  // + zoom réglable plutôt qu'un plafonnement — un index plutôt qu'un
  // curseur continu, plus simple à piloter aux boutons +/- comme sur
  // mobile).
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
  // Planning PAR CANAL de diffusion : l'onglet actif filtre tout — vue
  // calendrier, vue liste — et toute création se fait sur ce canal. Ouvrable
  // directement sur un canal donné via ?channel= (liens des tableaux de bord).
  const [channel, setChannel] = useState<ChannelValue>(() => {
    if (typeof window === "undefined") return "cable";
    // Ancien lien ?channel=radio : voie radio réseau (cf. lib/scheduleChannels.ts).
    return parseScheduleChannel(new URLSearchParams(window.location.search).get("channel"));
  });

  // La vue Semaine (7 colonnes proportionnelles à la minute) n'est pas
  // exploitable sur un écran de téléphone :
  // bascule sur la vue Jour, seule granularité "timeline" qui garde un sens
  // en une seule colonne — l'utilisateur garde aussi la vue Liste, les deux
  // seules proposées sur mobile (le sélecteur masque Semaine dans ce cas).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise avec le viewport (matchMedia), motif déjà accepté ailleurs (useIsMobile, ClientLayout)
    if (isMobile && viewMode === "week") setViewMode("day");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMobile]);

  // Bibliothèque rapide glisser-déposer : repliée par défaut sur
  // téléphone — le
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
  // Fenêtre radio : sans effet pour video/playlist.
  const [formEndTime, setFormEndTime] = useState<string>("20:00");
  const [formIs24_7, setFormIs24_7] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState(false);

  // Confirmation de suppression (destructive)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [scheduleToDeleteId, setScheduleToDeleteId] = useState<number | null>(null);

  // Glisser-déposer depuis la bibliothèque rapide — `durationMinutes` et
  // `label` capturés au `dragstart` (pas re-dérivés à chaque `dragover`)
  // alimentent le bloc fantôme proportionnel affiché pendant le survol.
  const [dragPayload, setDragPayload] = useState<{ type: TargetType; id: number; durationMinutes: number; label: string } | null>(null);
  const [dragOverDay, setDragOverDay] = useState<number | null>(null);
  // Minute du jour (0-1439) survolée pendant le drag, arrondie au 1/4 d'heure
  // — null tant qu'aucun survol de zone de dépôt n'est en cours.
  const [dragOverMinutes, setDragOverMinutes] = useState<number | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [librarySearch, setLibrarySearch] = useState("");
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);

  const showToast = (message: string, type: ToastState["type"] = "success") => setToast({ message, type });

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (viewMode === "week" || viewMode === "day") {
      const targetScroll = Math.max(0, 450 * pxPerMinute - 20);
      if (timelineScrollRef.current) {
        timelineScrollRef.current.scrollTop = targetScroll;
      }
    }
  }, [viewMode, channel, pxPerMinute]);

  const weekEndExclusive = useMemo(() => addDays(weekStart, 7), [weekStart]);

  // Sortie actuellement affichée par l'écran câblé : sert uniquement à avertir, sur la voie
  // « radio câblée », qu'une programmation ne s'entendra pas tant que l'écran n'est pas en mode Radio.
  const [cableOutput, setCableOutput] = useState<string | null>(null);
  useEffect(() => {
    if (channel !== "radio_cable") return;
    let cancelled = false;
    fetch(getApiUrl("/settings/display-output"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data && typeof data.cable === "string") setCableOutput(data.cable);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [channel]);

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

  const filteredVideos = videos.filter((v) => matchesQuery(v.title, librarySearch));
  const filteredPlaylists = playlists.filter((p) => matchesQuery(p.name, librarySearch));

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

  // Bascule Jour/Semaine/Liste : en passant en vue Jour, aligne le jour
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
    // Le canal radio n'a qu'un seul type de cible : pas de
    // toggle vidéo/playlist à afficher dans ce cas (cf. JSX du tiroir).
    setFormTargetType(isRadioLane(channel) ? "radio_playlist" : "video");
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

  const openCreateDrawer = (
    presetDate?: Date,
    preset?: { type: TargetType; id: number },
    exactTime = false
  ) => {
    resetForm();
    setEditingId(null);
    if (presetDate) {
      const withTime = new Date(presetDate);
      // Clic simple sur la timeline (pas d'heure précise à respecter) :
      // arrondi à l'heure suivante, comportement historique. Dépôt
      // glisser-déposer (`exactTime`) : l'heure/minute exacte du point de
      // dépôt est déjà calculée par l'appelant (cf. handleDropOnDay) et ne
      // doit pas être écrasée ici.
      if (!exactTime) {
        withTime.setHours(withTime.getHours() + 1, 0, 0, 0);
      }
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
      // Une programmation appartient au canal de l'onglet actif.
      channel,
    };
    if (formScheduleType === "once") {
      payload.run_at = new Date(formDateTime).toISOString();
    } else {
      payload.days_of_week = formDaysOfWeek;
      payload.time_of_day = formTime;
      // Fenêtre radio : sans effet côté backend pour
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
  // Overrides — actions rapides sur une occurrence
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
  // Glisser-déposer bibliothèque -> jour
  // --------------------------------------------------------------------
  const handleDropOnDay = (dayIndex: number) => {
    const minutes = dragOverMinutes;
    setDragOverDay(null);
    setDragOverMinutes(null);
    if (!dragPayload) return;
    const dropDate = new Date(weekDays[dayIndex]);
    if (minutes != null) {
      // Heure/minute EXACTES du point de dépôt (calculées pendant le
      // survol, cf. onDragOver ci-dessous) plutôt que de laisser
      // l'utilisateur ressaisir manuellement l'heure dans le formulaire —
      // corrige le constat "le drag and drop n'est pas intuitif" :
      // déposer à 18h32 pré-remplit bien 18h32, pas une heure arrondie
      // sans rapport avec l'endroit réellement visé.
      dropDate.setHours(0, minutes, 0, 0);
    }
    openCreateDrawer(dropDate, dragPayload, minutes != null);
    setDragPayload(null);
  };

  // Couleur du thème plutôt que du programme du cours.
  const getProgramAccent = () => "var(--accent-primary)";

  // Panneau d'actions rapides (édition/annulation/rétablissement/remplacement
  // d'une occurrence) — factorisé pour être partagé entre la chip de
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
                <ResponsiveSelect
                  value={replaceValue}
                  onChange={setReplaceValue}
                  placeholder={t("schedule.replaceWith")}
                  title={t("schedule.replaceWith")}
                  style={{ width: "100%", minHeight: "26px", fontSize: "0.7rem" }}
                  options={
                    o.target_type === "radio_playlist"
                      ? radioPlaylists.map((p) => ({ value: `radio_playlist:${p.id}`, label: p.name, group: t("schedule.radioPlaylistsGroup") }))
                      : [
                          ...videos.map((v) => ({ value: `video:${v.id}`, label: v.title, group: t("schedule.videosGroup") })),
                          ...playlists.map((p) => ({ value: `playlist:${p.id}`, label: p.name, group: t("schedule.playlistsGroup") })),
                        ]
                  }
                />
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

  // Bloc proportionnel à la durée (vues Jour/Semaine) :
  // positionné en absolu dans sa colonne via `style` (top/height calculés
  // par l'appelant selon pxPerMinute), miniature par type de média,
  // indicateur de chevauchement au tap (pas de survol au tactile).
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

  // Bande de fond "ambiance permanente 24/7" : un vrai calque
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

  const renderTimeAxis = () => (
    <div className="schedule-timeline-time-axis">
      <div className="schedule-axis-header">
        <Icon name="schedule" size={16} />
      </div>
      <div className="schedule-timeline-axis-track" style={{ height: MINUTES_PER_DAY * pxPerMinute }}>
        {Array.from({ length: 24 }, (_, hour) => (
          <div key={hour} className="schedule-timeline-axis-hour" style={{ height: HOUR_HEIGHT }}>
            <span>{`${hour.toString().padStart(2, "0")}:00`}</span>
          </div>
        ))}
      </div>
    </div>
  );

  const renderTimelineColumn = (day: Date, dayIndex: number, dayOccurrences: Occurrence[]) => {
    const isToday = isSameLocalDay(day, todayRef);
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    const bands = dayOccurrences.filter((o) => getOccurrenceWindow(o).isBackgroundBand);
    const timedOccurrences = dayOccurrences.filter((o) => !getOccurrenceWindow(o).isBackgroundBand);
    const cutsPreviousKeys = computeCutsPrevious(timedOccurrences);

    const isDragOverThisDay = dragOverDay === dayIndex && dragOverMinutes != null && dragPayload;

    return (
      <div key={dayIndex} className={`schedule-timeline-column ${isToday ? "today" : ""}`}>
        <div
          className={`schedule-timeline-track ${dragOverDay === dayIndex ? "drag-over" : ""}`}
          style={{ height: MINUTES_PER_DAY * pxPerMinute }}
          onClick={() => openCreateDrawer(day)}
          onDragOver={(e) => {
            e.preventDefault();
            const rect = e.currentTarget.getBoundingClientRect();
            const rawMinutes = (e.clientY - rect.top) / pxPerMinute;
            // Calé au 1/4 d'heure : un dépôt au pixel près serait
            // illisible une fois reporté dans le formulaire (ex. "18:31"),
            // et rien n'oblige une précision à la minute pour programmer un
            // cours.
            const snapped = Math.round(rawMinutes / 15) * 15;
            const clamped = Math.min(Math.max(snapped, 0), MINUTES_PER_DAY - 15);
            setDragOverDay(dayIndex);
            setDragOverMinutes(clamped);
          }}
          onDragLeave={() => {
            setDragOverDay(null);
            setDragOverMinutes(null);
          }}
          onDrop={() => handleDropOnDay(dayIndex)}
        >
          {bands.map(renderBackgroundBand)}
          {Array.from({ length: 24 }, (_, hour) => (
            <div key={hour} className="schedule-timeline-hour-row" style={{ height: HOUR_HEIGHT }}>
              <span className="schedule-timeline-hour-label">{`${hour.toString().padStart(2, "0")}:00`}</span>
            </div>
          ))}
          {isToday && (
            <div
              className="schedule-timeline-now-line"
              style={{ top: currentMinutes * pxPerMinute }}
              title={t("schedule.today")}
            >
              <span className="schedule-timeline-now-dot" />
            </div>
          )}
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
          {/* Bloc fantôme pendant le survol en drag : prévisualise la durée
              réelle du média glissé (proportionnelle, même échelle
              pxPerMinute que les blocs réels) et l'heure de dépôt calculée —
              remplace le simple contour pointillé générique sur toute la
              colonne, qui ne donnait aucun aperçu du contenu ni de l'heure
              visée. */}
          {isDragOverThisDay && (
            <div
              className="schedule-timeline-ghost"
              style={{
                position: "absolute",
                top: dragOverMinutes! * pxPerMinute,
                height: Math.max(dragPayload!.durationMinutes, MIN_BLOCK_MINUTES) * pxPerMinute,
                left: 4,
                right: 4,
                zIndex: 2,
              }}
            >
              <span className="schedule-timeline-ghost-time">{minutesToHHMM(dragOverMinutes!)}</span>
              <span className="schedule-timeline-ghost-label">{dragPayload!.label}</span>
            </div>
          )}
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

      <div className="schedule-toolbar sticky-glass-toolbar">
        {/* Onglets de canal : tout ce qui suit — calendrier,
            liste, créations — ne concerne que le canal sélectionné. */}
        <ScrollNav>
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
            className={`view-btn olc-press ${channel === "radio_cable" ? "active" : ""}`}
            onClick={() => setChannel("radio_cable")}
            title={t("schedule.channelRadioCableTitle")}
            style={{ display: "flex", alignItems: "center", gap: "6px", padding: "0 12px" }}
          >
            <Icon name="graphic_eq" size={16} />
            {t("schedule.channelTabRadioCable")}
          </button>
          <button
            className={`view-btn olc-press ${channel === "radio_network" ? "active" : ""}`}
            onClick={() => setChannel("radio_network")}
            title={t("schedule.channelRadioNetworkTitle")}
            style={{ display: "flex", alignItems: "center", gap: "6px", padding: "0 12px" }}
          >
            <Icon name="graphic_eq" size={16} />
            {t("schedule.channelTabRadioNetwork")}
          </button>
        </ScrollNav>
        {viewMode === "day" ? (
          <div className="week-nav">
            <button className="btn btn-secondary btn-sm" onClick={goToPreviousDay} title={t("schedule.previousDayTitle")}>
              <Icon name="chevron_left" size={16} />
              <span className="week-nav-btn-text">{t("schedule.previousWeekShort")}</span>
            </button>
            <button className="btn btn-secondary btn-sm" onClick={goToTodayDay}>
              {t("schedule.today")}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={goToNextDay} title={t("schedule.nextDayTitle")}>
              <span className="week-nav-btn-text">{t("schedule.nextWeekShort")}</span>
              <Icon name="chevron_right" size={16} />
            </button>
            <span className="week-nav-label">
              {DAY_LABELS_FULL[(dayViewDate.getDay() + 6) % 7]} {dayViewDate.toLocaleDateString(language === "fr" ? "fr-FR" : "en-US", { day: "numeric", month: "short" })}
            </span>
          </div>
        ) : (
          <div className="week-nav">
            <button className="btn btn-secondary btn-sm" onClick={goToPreviousWeek} title={t("schedule.previousWeekTitle")}>
              <Icon name="chevron_left" size={16} />
              <span className="week-nav-btn-text">{t("schedule.previousWeekShort")}</span>
            </button>
            <button className="btn btn-secondary btn-sm" onClick={goToToday}>
              {t("schedule.today")}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={goToNextWeek} title={t("schedule.nextWeekTitle")}>
              <span className="week-nav-btn-text">{t("schedule.nextWeekShort")}</span>
              <Icon name="chevron_right" size={16} />
            </button>
            <span className="week-nav-label">{formatWeekLabel(weekStart, language)}</span>
          </div>
        )}

        <div style={{ display: "flex", gap: "8px", alignItems: "center", flexShrink: 0 }}>
          {viewMode !== "list" && (
            <div className="view-toggle" title={t("schedule.zoomTitle")}>
              <button
                type="button"
                className="view-btn olc-press"
                onClick={() => setZoomIndex((z) => Math.max(0, z - 1))}
                disabled={zoomIndex === 0}
                title={t("schedule.zoomOutTitle")}
                style={{ padding: "4px 8px" }}
              >
                <Icon name="zoom_out" size={16} />
              </button>
              <button
                type="button"
                className="view-btn olc-press"
                onClick={() => setZoomIndex((z) => Math.min(ZOOM_LEVELS.length - 1, z + 1))}
                disabled={zoomIndex === ZOOM_LEVELS.length - 1}
                title={t("schedule.zoomInTitle")}
                style={{ padding: "4px 8px" }}
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
              style={{ padding: "4px 10px" }}
            >
              <Icon name="view_day" size={17} />
            </button>
            {!isMobile && (
              <button
                className={`view-btn olc-press ${viewMode === "week" ? "active" : ""}`}
                onClick={() => setViewMode("week")}
                title={t("schedule.weekView")}
                style={{ padding: "4px 10px" }}
              >
                <Icon name="calendar_view_week" size={17} />
              </button>
            )}
            <button
              className={`view-btn olc-press ${viewMode === "list" ? "active" : ""}`}
              onClick={() => setViewMode("list")}
              title={t("schedule.listView")}
              style={{ padding: "4px 10px" }}
            >
              <Icon name="view_list" size={17} />
            </button>
          </div>
          {!isRadioLane(channel) && (
            <button
              type="button"
              className={`view-btn olc-press ${libraryOpen ? "active" : ""}`}
              onClick={() => setLibraryOpen((open) => !open)}
              title={t("schedule.quickLibrary")}
              style={{ display: "inline-flex", alignItems: "center", gap: "6px", height: "34px", padding: "0 10px", borderRadius: "var(--radius-sm)", flexShrink: 0 }}
            >
              <Icon name="video_library" size={16} />
              <span className="hidden-sm">{t("nav.library")}</span>
            </button>
          )}
          <button
            className="btn btn-primary"
            onClick={() => openCreateDrawer()}
            style={{ height: "34px", padding: "0 12px", fontSize: "0.85rem", whiteSpace: "nowrap", flexShrink: 0 }}
          >
            <Icon name="add" size={18} />
            <span className="schedule-btn-text-full">{t("schedule.newSchedule")}</span>
            <span className="schedule-btn-text-short">{t("schedule.newScheduleShort")}</span>
          </button>
        </div>
      </div>

      {/* Voie « radio câblée » alors que l'écran câblé n'est pas en mode Radio : la playlist d'une
          programmation se charge en pause sans basculer l'écran (jamais de bascule implicite). */}
      {channel === "radio_cable" && cableOutput !== null && cableOutput !== "radio" && (
        <div className="interrupted-block" role="status">
          <div className="interrupted-text">
            <span className="interrupted-label">{t("schedule.radioCableAutoSwitchHint")}</span>
          </div>
        </div>
      )}

      <div className="schedule-body" style={{ flexDirection: isMobile ? "column" : "row", gap: "20px" }}>
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>
          {loading ? (
            <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              {t("schedule.loadingSchedule")}
            </div>
          ) : viewMode === "week" ? (
            <div className="schedule-timeline-scroll" ref={timelineScrollRef}>
              <div className="schedule-timeline-week-grid">
                {renderTimeAxis()}
                {weekDays.map((day, index) => {
                  const isDayToday = isSameLocalDay(day, todayRef);
                  return (
                    <div key={index} className={`schedule-timeline-week-col ${isDayToday ? "today" : ""}`}>
                      <div className="schedule-day-header">
                        <span className="schedule-day-header-name">{DAY_LABELS_FULL[index]}</span>
                        <span className="schedule-day-header-date">{day.getDate()}</span>
                      </div>
                      {renderTimelineColumn(day, index, occurrencesByDay[index])}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : viewMode === "day" ? (
            <div className="schedule-timeline-scroll" ref={timelineScrollRef}>
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

        {/* Bibliothèque rapide (glisser-déposer sur un jour) : le
            glisser-déposer HTML5 n'existe pas au toucher, ce panneau reste
            surtout un raccourci de recherche sur téléphone — d'où la largeur
            pleine plutôt que la colonne fixe du PC. Sans objet sur le canal
            radio : un seul type de cible (playlist radio), pas
            de bibliothèque vidéo/playlist à glisser-déposer ici. */}
        {/* Playlists radio SUGGÉRÉES d'emblée (aucune recherche à faire) : cartes avec pochette, durée et
            nombre de titres, à glisser sur un jour ou à toucher pour programmer — même principe que la
            bibliothèque rapide des vidéos. */}
        {libraryOpen && isRadioLane(channel) && (
          <div className="library-picker glass-floating" style={{ width: isMobile ? "100%" : "260px", height: "auto", flexShrink: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="form-label" style={{ margin: 0 }}>
                {t("schedule.radioQuickLibrary")}
              </span>
              <button className="close-btn" onClick={() => setLibraryOpen(false)} title={t("schedule.hide")}>
                <Icon name="close" size={16} />
              </button>
            </div>
            <SearchBox
              className="form-control"
              placeholder={t("schedule.searchPlaceholder")}
              value={librarySearch}
              onChange={setLibrarySearch}
              suggestions={radioPlaylists.map((p) => p.name)}
              style={{ height: "32px", fontSize: "0.8rem" }}
            />
            <p style={{ fontSize: "0.7rem", color: "var(--text-dim)", margin: 0 }}>{t("schedule.radioDragHint")}</p>
            <div className="library-picker-list">
              {radioPlaylists
                .filter((p) => matchesQuery(p.name, librarySearch))
                .map((p) => {
                  const cover = p.cover_track_id != null ? getApiUrl(`/radio/tracks/${p.cover_track_id}/cover`) : null;
                  const durationMinutes = p.total_duration_seconds ? Math.max(p.total_duration_seconds / 60, MIN_BLOCK_MINUTES) : MIN_BLOCK_MINUTES;
                  return (
                    <div
                      key={`rp-${p.id}`}
                      className={`picker-card ${isMobile ? "always-show-add" : ""}`}
                      draggable
                      role="button"
                      tabIndex={0}
                      title={p.name}
                      onClick={() => openCreateDrawer(undefined, { type: "radio_playlist", id: p.id })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          openCreateDrawer(undefined, { type: "radio_playlist", id: p.id });
                        }
                      }}
                      onDragStart={(e) => {
                        e.dataTransfer.setData("text/plain", String(p.id));
                        setDragPayload({ type: "radio_playlist", id: p.id, durationMinutes, label: p.name });
                      }}
                      onDragEnd={() => {
                        setDragPayload(null);
                        setDragOverDay(null);
                        setDragOverMinutes(null);
                      }}
                    >
                      <div className="thumbnail-wrapper">
                        {cover ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={cover} alt="" className="card-thumbnail" />
                        ) : (
                          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Icon name="queue_music" size={20} style={{ opacity: 0.25 }} />
                          </div>
                        )}
                        <span className="card-duration" style={{ fontSize: "0.65rem", padding: "1px 4px" }}>
                          {formatDuration(p.total_duration_seconds)}
                        </span>
                      </div>
                      <div className="picker-card-content">
                        <span className="picker-card-title">
                          <Icon name={p.is_default ? "star" : "queue_music"} size={12} /> {p.name}
                        </span>
                        <div className="picker-card-meta">
                          <span className="release-badge" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                            {t("schedule.tracksCount", { count: p.item_count })}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              {radioPlaylists.length === 0 && (
                <div style={{ gridColumn: "1 / -1", textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem", padding: "12px" }}>
                  {t("schedule.noRadioPlaylists")}
                </div>
              )}
              {radioPlaylists.length > 0 && radioPlaylists.every((p) => !matchesQuery(p.name, librarySearch)) && (
                <div style={{ gridColumn: "1 / -1", textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem", padding: "12px" }}>
                  {t("schedule.noResults")}
                </div>
              )}
            </div>
          </div>
        )}

        {libraryOpen && !isRadioLane(channel) && (
          <div className="library-picker glass-floating" style={{ width: isMobile ? "100%" : "260px", height: "auto", flexShrink: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="form-label" style={{ margin: 0 }}>
                {t("schedule.quickLibrary")}
              </span>
              <button className="close-btn" onClick={() => setLibraryOpen(false)} title={t("schedule.hide")}>
                <Icon name="close" size={16} />
              </button>
            </div>
            <SearchBox
              className="form-control"
              placeholder={t("schedule.searchPlaceholder")}
              value={librarySearch}
              onChange={setLibrarySearch}
              suggestions={[...videos.map((v) => v.title), ...playlists.map((p) => p.name)]}
              style={{ height: "32px", fontSize: "0.8rem" }}
            />
            <p style={{ fontSize: "0.7rem", color: "var(--text-dim)", margin: 0 }}>
              {t("schedule.dragHint")}
            </p>
            <div className="library-picker-list">
              {/* Carte visuelle (miniature + titre + type/durée) plutôt
                  qu'une ligne de texte brut sans affordance ni preview —
                  répond au constat "il manque un style d'encadré avec
                  prévu de la miniature, type du cours etc". Même patron
                  `.picker-card` que la Bibliothèque/les playlists
                  (VideoPlaylistManager), pour une cohérence visuelle avec
                  le reste de l'app. `dataTransfer.setData` posé pour une
                  conformité multi-navigateur (Firefox en particulier,
                  cible de support officiel) : sans
                  lui, le drag natif peut ne pas s'amorcer sur certains
                  navigateurs. Aucun `setDragImage` manuel : le navigateur
                  utilise par défaut un instantané de cette carte, déjà une
                  vraie preview visuelle (miniature incluse) sans code
                  supplémentaire. */}
              {filteredVideos.map((v) => {
                const thumbSrc = getThumbnailSrc(v.thumbnail_path);
                const durationMinutes = v.duration_seconds ? Math.max(v.duration_seconds / 60, MIN_BLOCK_MINUTES) : MIN_BLOCK_MINUTES;
                return (
                  <div
                    key={`v-${v.id}`}
                    className={`picker-card ${isMobile ? "always-show-add" : ""}`}
                    draggable
                    title={v.title}
                    onDragStart={(e) => {
                      e.dataTransfer.setData("text/plain", String(v.id));
                      setDragPayload({ type: "video", id: v.id, durationMinutes, label: v.title });
                    }}
                    onDragEnd={() => {
                      setDragPayload(null);
                      setDragOverDay(null);
                      setDragOverMinutes(null);
                    }}
                  >
                    <div className="thumbnail-wrapper">
                      {thumbSrc ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={thumbSrc} alt="" className="card-thumbnail" />
                      ) : (
                        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Icon name="movie" size={20} style={{ opacity: 0.25 }} />
                        </div>
                      )}
                      <span className="card-duration" style={{ fontSize: "0.65rem", padding: "1px 4px" }}>
                        {formatDuration(v.duration_seconds)}
                      </span>
                    </div>
                    <div className="picker-card-content">
                      <span className="picker-card-title">{v.title}</span>
                      {v.program && (
                        <div className="picker-card-meta">
                          <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                            {v.program}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              {filteredPlaylists.map((p) => {
                const thumbSrc = getThumbnailSrc(p.thumbnail_path);
                const durationMinutes = p.total_duration_seconds ? Math.max(p.total_duration_seconds / 60, MIN_BLOCK_MINUTES) : MIN_BLOCK_MINUTES;
                return (
                  <div
                    key={`p-${p.id}`}
                    className={`picker-card ${isMobile ? "always-show-add" : ""}`}
                    draggable
                    title={p.name}
                    onDragStart={(e) => {
                      e.dataTransfer.setData("text/plain", String(p.id));
                      setDragPayload({ type: "playlist", id: p.id, durationMinutes, label: p.name });
                    }}
                    onDragEnd={() => {
                      setDragPayload(null);
                      setDragOverDay(null);
                      setDragOverMinutes(null);
                    }}
                  >
                    <div className="thumbnail-wrapper">
                      {thumbSrc ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={thumbSrc} alt="" className="card-thumbnail" />
                      ) : (
                        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Icon name="playlist_play" size={20} style={{ opacity: 0.25 }} />
                        </div>
                      )}
                      <span className="card-duration" style={{ fontSize: "0.65rem", padding: "1px 4px" }}>
                        {formatDuration(p.total_duration_seconds)}
                      </span>
                    </div>
                    <div className="picker-card-content">
                      <span className="picker-card-title">
                        <Icon name="playlist_play" size={12} /> {p.name}
                      </span>
                      <div className="picker-card-meta">
                        <span className="release-badge" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                          {t("schedule.coursesCount", { count: p.item_count })}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
              {filteredVideos.length === 0 && filteredPlaylists.length === 0 && (
                <div style={{ gridColumn: "1 / -1", textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem", padding: "12px" }}>
                  {t("schedule.noResults")}
                </div>
              )}
            </div>
          </div>
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
                  {isRadioLane(channel) ? t("schedule.radioPlaylistLabel") : t("schedule.targetLabel")}
                </label>
                {/* Le canal radio n'a qu'un seul type de cible (playlist
                    radio) : pas de toggle à afficher, contrairement
                    au câblé/réseau qui choisissent entre vidéo et playlist. */}
                {!isRadioLane(channel) && (
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
                <SearchBox
                  className="form-control"
                  placeholder={t("schedule.searchPlaceholder")}
                  value={formTargetSearch}
                  onChange={setFormTargetSearch}
                  suggestions={targetOptions.map((opt) => opt.label)}
                />
                <div className="library-picker-list" style={{ maxHeight: isRadioLane(channel) ? "260px" : "160px" }}>
                  {targetOptions
                    .filter((opt) => matchesQuery(opt.label, formTargetSearch))
                    .map((opt) => {
                      const selected = String(opt.id) === formTargetId;
                      const radioPlaylist = isRadioLane(channel) ? findRadioPlaylist(opt.id) : undefined;
                      if (radioPlaylist) {
                        // Playlist radio : pochette, durée et nombre de titres visibles AVANT toute recherche.
                        const cover = radioPlaylist.cover_track_id != null ? getApiUrl(`/radio/tracks/${radioPlaylist.cover_track_id}/cover`) : null;
                        return (
                          <div
                            key={opt.id}
                            className="library-picker-item"
                            role="option"
                            aria-selected={selected}
                            tabIndex={0}
                            style={{
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              borderColor: selected ? "var(--accent-primary)" : undefined,
                              background: selected ? "color-mix(in srgb, var(--accent-primary) 8%, transparent)" : undefined,
                            }}
                            onClick={() => setFormTargetId(String(opt.id))}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                setFormTargetId(String(opt.id));
                              }
                            }}
                          >
                            {cover ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={cover} alt="" style={{ width: 44, height: 44, borderRadius: 6, objectFit: "cover", flexShrink: 0 }} />
                            ) : (
                              <span style={{ width: 44, height: 44, borderRadius: 6, flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center", background: "var(--bg-surface-elevated)" }}>
                                <Icon name="queue_music" size={20} style={{ opacity: 0.4 }} />
                              </span>
                            )}
                            <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                <Highlight text={opt.label} query={formTargetSearch} />
                              </span>
                              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                                {t("schedule.tracksCount", { count: radioPlaylist.item_count })} · {formatDuration(radioPlaylist.total_duration_seconds)}
                              </span>
                            </span>
                            {selected && <Icon name="check" size={18} />}
                          </div>
                        );
                      }
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

                  {/* Fenêtre radio : sans objet pour
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

      {/* Confirmation de suppression (destructive) */}
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
