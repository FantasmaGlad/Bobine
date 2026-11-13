"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { Rule, RuleTarget, RuleType } from "./types";

interface RulesPanelProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  rules: Rule[];
  setRules: React.Dispatch<React.SetStateAction<Rule[]>>;
  fetchAll: () => void;
  showToast: ShowToast;
  targetOptions: { value: string; label: string }[];
}

export default function RulesPanel({ t, rules, setRules, fetchAll, showToast, targetOptions }: RulesPanelProps) {
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

  const ruleLabel = (type: RuleType) =>
    type === "every_n_tracks"
      ? t("radioAnnouncements.ruleTypeEveryNTracks")
      : type === "every_x_minutes"
      ? t("radioAnnouncements.ruleTypeEveryXMinutes")
      : t("radioAnnouncements.ruleTypeFixedTimes");

  const ruleDetail = (rule: Rule) =>
    rule.rule_type === "every_n_tracks"
      ? `${rule.n_tracks}`
      : rule.rule_type === "every_x_minutes"
      ? `${rule.interval_minutes} min`
      : (rule.times_of_day || []).join(", ");

  const targetLabel = (target: RuleTarget) =>
    target === "radio_cable"
      ? t("radioAnnouncements.targetCable")
      : target === "both"
      ? t("radioAnnouncements.targetBoth")
      : t("radioAnnouncements.targetNetwork");


  const ruleIcon = (type: RuleType) =>
    type === "every_n_tracks" ? "music_note" : type === "every_x_minutes" ? "timer" : "schedule";

  return (
        <section className="ra-col">
          <div className="ra-card">
            <h3 className="ra-card-title"><Icon name="schedule" size={18} /> {t("radioAnnouncements.rulesTitle")}</h3>
            <p className="ra-card-hint">{t("radioAnnouncements.rulesHint")}</p>

            {rules.length === 0 ? (
              <p className="live-empty" style={{ marginBottom: "12px" }}>{t("radioAnnouncements.noRules")}</p>
            ) : (
              <div className="ra-list" style={{ marginBottom: "16px" }}>
                {rules.map((rule) => (
                  <div key={rule.id} className={`ra-rule ${rule.enabled ? "" : "off"}`}>
                    <div className="ra-rule-icon"><Icon name={ruleIcon(rule.rule_type)} size={18} /></div>
                    <div className="ra-rule-info">
                      <span className="ra-rule-type">{ruleLabel(rule.rule_type)}</span>
                      <span className="ra-rule-detail">{ruleDetail(rule)} · {targetLabel(rule.target)}</span>
                    </div>
                    <label className="ra-switch" title={t("radioAnnouncements.enabledLabel")}>
                      <input type="checkbox" checked={rule.enabled} onChange={() => toggleRuleEnabled(rule)} />
                      <span className="ra-switch-track" />
                    </label>
                    <button className="btn btn-danger ra-icon-btn" onClick={() => handleDeleteRule(rule.id)} title={t("radioAnnouncements.delete")}><Icon name="delete" size={16} /></button>
                  </div>
                ))}
              </div>
            )}

            <div className="ra-add-rule">
              <span className="ra-field-label">{t("radioAnnouncements.addRuleTitle")}</span>
              <ResponsiveSelect
                className="form-control"
                value={newRuleType}
                onChange={(value) => setNewRuleType(value as RuleType)}
                title={t("radioAnnouncements.addRuleTitle")}
                options={[
                  { value: "every_n_tracks", label: t("radioAnnouncements.ruleTypeEveryNTracks") },
                  { value: "every_x_minutes", label: t("radioAnnouncements.ruleTypeEveryXMinutes") },
                  { value: "fixed_times", label: t("radioAnnouncements.ruleTypeFixedTimes") },
                ]}
              />

              <ResponsiveSelect
                className="form-control"
                value={newRuleTarget}
                onChange={(value) => setNewRuleTarget(value as RuleTarget)}
                title={t("radioAnnouncements.ruleTargetTitle")}
                options={targetOptions}
              />

              {newRuleType === "every_n_tracks" && (
                <input type="number" min={1} className="form-control" value={newNTracks}
                  onChange={(e) => setNewNTracks(e.target.value)} placeholder={t("radioAnnouncements.nTracksLabel")} />
              )}
              {newRuleType === "every_x_minutes" && (
                <input type="number" min={1} className="form-control" value={newIntervalMinutes}
                  onChange={(e) => setNewIntervalMinutes(e.target.value)} placeholder={t("radioAnnouncements.intervalMinutesLabel")} />
              )}
              {newRuleType === "fixed_times" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input type="time" className="form-control" value={newTimeInput} onChange={(e) => setNewTimeInput(e.target.value)} style={{ flex: 1 }} />
                    <button className="btn btn-secondary" onClick={() => { if (newTimeInput && !newTimes.includes(newTimeInput)) setNewTimes((prev) => [...prev, newTimeInput].sort()); }}>
                      <Icon name="add" size={16} /> {t("radioAnnouncements.addTime")}
                    </button>
                  </div>
                  {newTimes.length === 0 ? (
                    <span className="live-empty">{t("radioAnnouncements.noTimes")}</span>
                  ) : (
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                      {newTimes.map((tm) => (
                        <span key={tm} className="ra-time-pill" onClick={() => setNewTimes((prev) => prev.filter((x) => x !== tm))} title={t("radioAnnouncements.deleteRule")}>
                          {tm} <Icon name="close" size={12} />
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <button className="btn btn-primary" style={{ height: "44px" }} onClick={handleAddRule} disabled={newRuleType === "fixed_times" && newTimes.length === 0}>
                <Icon name="add" size={16} /> {t("radioAnnouncements.addRule")}
              </button>
            </div>
          </div>
        </section>
  );
}
