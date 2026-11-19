"use client";

import React from "react";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { Rule, RuleTarget, RuleType } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

const RULE_KEYS: Record<RuleType, string> = {
  every_n_tracks: "radioAnnouncements.ruleTypeEveryNTracks",
  every_x_minutes: "radioAnnouncements.ruleTypeEveryXMinutes",
  fixed_times: "radioAnnouncements.ruleTypeFixedTimes",
};

function ruleDetail(rule: Rule) {
  if (rule.rule_type === "every_n_tracks") return `${rule.n_tracks}`;
  if (rule.rule_type === "every_x_minutes") return `${rule.interval_minutes} min`;
  return (rule.times_of_day || []).join(", ");
}

function targetKey(target: RuleTarget) {
  if (target === "radio_cable") return "radioAnnouncements.targetCable";
  if (target === "both") return "radioAnnouncements.targetBoth";
  return "radioAnnouncements.targetNetwork";
}

const ruleIcon = (type: RuleType) => (type === "every_n_tracks" ? "music_note" : type === "every_x_minutes" ? "timer" : "schedule");

export function useRuleActions(t: Translate, showToast: ShowToast, setRules: React.Dispatch<React.SetStateAction<Rule[]>>) {
  const toggleRuleEnabled = async (rule: Rule) => {
    const res = await fetch(getApiUrl(`/radio/announcement-rules/${rule.id}`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rule_type: rule.rule_type, n_tracks: rule.n_tracks, interval_minutes: rule.interval_minutes,
        times_of_day: rule.times_of_day, enabled: !rule.enabled, target: rule.target,
      }),
    });
    if (res.ok) {
      setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, enabled: !r.enabled } : r)));
    } else {
      showToast(t("radioAnnouncements.ruleError"), "error");
    }
  };

  const handleDeleteRule = async (id: number) => {
    const res = await fetch(getApiUrl(`/radio/announcement-rules/${id}`), { method: "DELETE" });
    if (res.ok) {
      showToast(t("radioAnnouncements.ruleDeletedToast"));
      setRules((prev) => prev.filter((r) => r.id !== id));
    } else {
      showToast(t("radioAnnouncements.genericError"), "error");
    }
  };

  return { toggleRuleEnabled, handleDeleteRule };
}

export default function RuleRow({ t, rule, onToggle, onDelete }: { t: Translate; rule: Rule; onToggle: () => void; onDelete: () => void }) {
  return (
    <div className={`ra-rule ${rule.enabled ? "" : "off"}`}>
      <div className="ra-rule-icon"><Icon name={ruleIcon(rule.rule_type)} size={18} /></div>
      <div className="ra-rule-info">
        <span className="ra-rule-type">{t(RULE_KEYS[rule.rule_type] ?? RULE_KEYS.fixed_times)}</span>
        <span className="ra-rule-detail">{ruleDetail(rule)} · {t(targetKey(rule.target))}</span>
      </div>
      <label className="ra-switch" title={t("radioAnnouncements.enabledLabel")}>
        <input type="checkbox" checked={rule.enabled} onChange={onToggle} />
        <span className="ra-switch-track" />
      </label>
      <button className="btn btn-danger ra-icon-btn" onClick={onDelete} title={t("radioAnnouncements.delete")}><Icon name="delete" size={16} /></button>
    </div>
  );
}
