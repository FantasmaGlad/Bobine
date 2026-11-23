"use client";

import { useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { DEFAULT_RADIO_CHANNEL } from "@/lib/outputs";
import type { ShowToast } from "@/lib/useToast";
import type { RuleTarget } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function usePlayNow(t: Translate, showToast: ShowToast) {
  const [playNowTarget, setPlayNowTarget] = useState<RuleTarget>(DEFAULT_RADIO_CHANNEL);

  const handlePlayNow = async (announcementId?: number) => {
    const res = await fetch(getApiUrl("/radio/announcements/play-now"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ announcement_id: announcementId ?? null, target: playNowTarget }),
    });
    if (res.ok) {
      const data = await res.json();
      showToast(t("radioAnnouncements.playNowToast", { description: data.description }));
    } else {
      showToast(t("radioAnnouncements.playNowError"), "error");
    }
  };

  return { playNowTarget, setPlayNowTarget, handlePlayNow };
}
