"use client";

import React, { useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

import { parseIntOrNull, sendJson } from "./api";
import type { RadioTrack } from "./types";
import type { RadioCatalog } from "./useRadioCatalog";

export type TrackForm = Record<"title" | "artist" | "album" | "album_artist" | "track_number" | "disc_number" | "year" | "genre", string>;

const text = (value: string | number | null) => (value == null ? "" : String(value));

function formOf(track: RadioTrack): TrackForm {
  return {
    title: track.title, artist: text(track.artist), album: text(track.album), album_artist: text(track.album_artist),
    track_number: text(track.track_number), disc_number: text(track.disc_number), year: text(track.year), genre: text(track.genre),
  };
}

export function useTrackEditor(catalog: RadioCatalog, showToast: ShowToast) {
  const { t } = useAppSettings();
  const [track, setTrack] = useState<RadioTrack | null>(null);
  const [form, setForm] = useState<TrackForm>(() => formOf({ title: "" } as RadioTrack));
  const [tags, setTags] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState<RadioTrack | null>(null);

  const open = (next: RadioTrack) => {
    setTrack(next);
    setForm(formOf(next));
    setTags([...next.tags]);
  };

  const toggleTag = (name: string) => setTags((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]));
  const addTag = (name: string) => setTags((prev) => (prev.includes(name) ? prev : [...prev, name]));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!track || !form.title.trim()) {
      showToast(t("radioLibrary.saveError"), "warning");
      return;
    }
    setSaving(true);
    try {
      const res = await sendJson(`/radio/tracks/${track.id}`, "PUT", {
        title: form.title.trim(), artist: form.artist, album: form.album, album_artist: form.album_artist, genre: form.genre,
        track_number: parseIntOrNull(form.track_number), disc_number: parseIntOrNull(form.disc_number), year: parseIntOrNull(form.year), tags,
      });
      if (!res.ok) {
        showToast(t("radioLibrary.saveError"), "error");
        return;
      }
      const updated: RadioTrack = await res.json();
      setTrack(updated);
      setTags([...updated.tags]);
      showToast(t("radioLibrary.updatedToast"));
      catalog.refreshAll();
    } catch {
      showToast(t("radioLibrary.connectionError"), "error");
    } finally {
      setSaving(false);
    }
  };

  const uploadCover = async (file: File) => {
    if (!track) return;
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch(getApiUrl(`/radio/tracks/${track.id}/cover`), { method: "POST", body });
      if (!res.ok) throw new Error();
      setTrack(await res.json());
      catalog.bumpCovers();
      showToast(t("radioLibrary.coverUpdatedToast"));
      catalog.refreshAll();
    } catch {
      showToast(t("radioLibrary.coverError"), "error");
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    try {
      const res = await sendJson(`/radio/tracks/${toDelete.id}`, "DELETE");
      if (!res.ok) {
        showToast(t("radioLibrary.deleteError"), "error");
        return;
      }
      showToast(t("radioLibrary.deletedToast"));
      if (track?.id === toDelete.id) setTrack(null);
      catalog.refreshAll();
    } catch {
      showToast(t("radioLibrary.connectionError"), "error");
    } finally {
      setToDelete(null);
    }
  };

  return { track, close: () => setTrack(null), form, setForm, tags, toggleTag, addTag, saving, save, uploadCover, open, toDelete, setToDelete, remove };
}

export type TrackEditor = ReturnType<typeof useTrackEditor>;
