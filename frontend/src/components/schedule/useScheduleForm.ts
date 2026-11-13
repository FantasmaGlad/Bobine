"use client";

import React, { useState } from "react";

import { errorMessage } from "@/lib/apiError";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { isRadioLane } from "@/lib/scheduleChannels";
import { toDatetimeLocalValue, type ChannelValue, type ScheduleDetail, type ScheduleTypeValue, type TargetType } from "@/lib/scheduleTime";
import type { ShowToast } from "@/lib/useToast";

export interface ScheduleForm {
  targetType: TargetType;
  targetId: string;
  targetSearch: string;
  scheduleType: ScheduleTypeValue;
  dateTime: string;
  daysOfWeek: number[];
  time: string;
  active: boolean;
  endTime: string;
  is24_7: boolean;
}

function blankForm(channel: ChannelValue): ScheduleForm {
  return {
    targetType: isRadioLane(channel) ? "radio_playlist" : "video",
    targetId: "", targetSearch: "", scheduleType: "once", dateTime: "", daysOfWeek: [],
    time: "18:00", active: true, endTime: "20:00", is24_7: false,
  };
}

function formFrom(data: ScheduleDetail): ScheduleForm {
  return {
    targetType: data.target_type,
    targetId: String(data.target_id),
    targetSearch: "",
    scheduleType: data.schedule_type,
    dateTime: data.run_at ? toDatetimeLocalValue(new Date(data.run_at)) : "",
    daysOfWeek: data.days_of_week ?? [],
    time: data.time_of_day ?? "18:00",
    active: data.active,
    endTime: data.end_time ?? "20:00",
    is24_7: data.is_24_7 ?? false,
  };
}

function payloadOf(form: ScheduleForm, channel: ChannelValue): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    target_type: form.targetType, target_id: Number(form.targetId), schedule_type: form.scheduleType, active: form.active, channel,
  };
  if (form.scheduleType === "once") {
    payload.run_at = new Date(form.dateTime).toISOString();
    return payload;
  }
  payload.days_of_week = form.daysOfWeek;
  payload.time_of_day = form.time;
  if (form.targetType === "radio_playlist") {
    payload.is_24_7 = form.is24_7;
    if (!form.is24_7) payload.end_time = form.endTime;
  }
  return payload;
}

function missingField(form: ScheduleForm): string | null {
  if (!form.targetId) return "schedule.chooseTargetWarning";
  if (form.scheduleType === "once" && !form.dateTime) return "schedule.chooseDateTimeWarning";
  if (form.scheduleType === "recurring" && form.daysOfWeek.length === 0) return "schedule.chooseDayWarning";
  return null;
}

export function useScheduleForm(channel: ChannelValue, showToast: ShowToast, onChanged: () => void) {
  const { t } = useAppSettings();
  const [form, setForm] = useState<ScheduleForm>(() => blankForm(channel));
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [overrideCount, setOverrideCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const patch = (changes: Partial<ScheduleForm>) => setForm((prev) => ({ ...prev, ...changes }));

  const openCreate = (presetDate?: Date, preset?: { type: TargetType; id: number }, exactTime = false) => {
    const next = blankForm(channel);
    if (presetDate) {
      const withTime = new Date(presetDate);
      if (!exactTime) withTime.setHours(withTime.getHours() + 1, 0, 0, 0);
      next.dateTime = toDatetimeLocalValue(withTime);
    }
    if (preset) {
      next.targetType = preset.type;
      next.targetId = String(preset.id);
    }
    setForm(next);
    setOverrideCount(0);
    setEditingId(null);
    setOpen(true);
  };

  const openEdit = async (scheduleId: number) => {
    try {
      const res = await fetch(getApiUrl(`/schedule/${scheduleId}`), { cache: "no-store" });
      if (!res.ok) {
        showToast(t("schedule.loadScheduleError"), "error");
        return;
      }
      const data: ScheduleDetail = await res.json();
      setEditingId(data.id);
      setForm(formFrom(data));
      setOverrideCount(data.override_count);
      setOpen(true);
    } catch {
      showToast(t("schedule.networkError"), "error");
    }
  };

  const close = () => {
    setOpen(false);
    setEditingId(null);
  };

  const toggleDay = (day: number) =>
    setForm((prev) => ({
      ...prev,
      daysOfWeek: prev.daysOfWeek.includes(day) ? prev.daysOfWeek.filter((d) => d !== day) : [...prev.daysOfWeek, day].sort((a, b) => a - b),
    }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const missing = missingField(form);
    if (missing) {
      showToast(t(missing), "warning");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(getApiUrl(editingId ? `/schedule/${editingId}` : "/schedule"), {
        method: editingId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payloadOf(form, channel)),
      });
      if (res.ok) {
        showToast(editingId ? t("schedule.updatedToast") : t("schedule.createdToast"));
        close();
        onChanged();
      } else {
        const data = await res.json().catch(() => null);
        showToast(errorMessage(data, t("schedule.saveError")), "error");
      }
    } catch {
      showToast(t("schedule.saveNetworkError"), "error");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!editingId) return;
    try {
      const res = await fetch(getApiUrl(`/schedule/${editingId}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("schedule.deletedToast"));
        close();
        onChanged();
      } else {
        showToast(t("schedule.deleteError"), "error");
      }
    } catch {
      showToast(t("schedule.networkError"), "error");
    } finally {
      setConfirmDelete(false);
    }
  };

  return { form, patch, open, editingId, overrideCount, saving, confirmDelete, setConfirmDelete, openCreate, openEdit, close, toggleDay, save, remove };
}

export type ScheduleFormState = ReturnType<typeof useScheduleForm>;
