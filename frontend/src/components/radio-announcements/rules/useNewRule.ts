"use client";

import { useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { RuleTarget, RuleType } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function useNewRule(t: Translate, showToast: ShowToast, fetchAll: () => void) {
  const [newRuleType, setNewRuleType] = useState<RuleType>("every_n_tracks");
  const [newRuleTarget, setNewRuleTarget] = useState<RuleTarget>("radio_network");
  const [newNTracks, setNewNTracks] = useState("5");
  const [newIntervalMinutes, setNewIntervalMinutes] = useState("30");
  const [newTimes, setNewTimes] = useState<string[]>([]);
  const [newTimeInput, setNewTimeInput] = useState("09:00");

  const handleAddRule = async () => {
    const payload: Record<string, unknown> = { rule_type: newRuleType, enabled: true, target: newRuleTarget };
    if (newRuleType === "every_n_tracks") payload.n_tracks = Number(newNTracks);
    if (newRuleType === "every_x_minutes") payload.interval_minutes = Number(newIntervalMinutes);
    if (newRuleType === "fixed_times") payload.times_of_day = newTimes;

    const res = await fetch(getApiUrl("/radio/announcement-rules"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast(t("radioAnnouncements.ruleSavedToast"));
      setNewTimes([]);
      fetchAll();
    } else {
      const data = await res.json().catch(() => null);
      showToast(errorMessage(data, t("radioAnnouncements.ruleError")), "error");
    }
  };

  const addTime = () => { if (newTimeInput && !newTimes.includes(newTimeInput)) setNewTimes((prev) => [...prev, newTimeInput].sort()); };
  const removeTime = (tm: string) => setNewTimes((prev) => prev.filter((x) => x !== tm));

  return {
    newRuleType, setNewRuleType, newRuleTarget, setNewRuleTarget, newNTracks, setNewNTracks, newIntervalMinutes, setNewIntervalMinutes,
    newTimes, newTimeInput, setNewTimeInput, addTime, removeTime, handleAddRule,
  };
}
