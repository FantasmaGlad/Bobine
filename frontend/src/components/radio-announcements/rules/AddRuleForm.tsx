"use client";

import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import type { RuleTarget, RuleType } from "../types";
import FixedTimesInput from "./FixedTimesInput";
import type { useNewRule } from "./useNewRule";

export default function AddRuleForm({ t, rule, targetOptions }: {
  t: (key: string, vars?: Record<string, string | number>) => string; rule: ReturnType<typeof useNewRule>; targetOptions: { value: string; label: string }[];
}) {
  const { newRuleType, setNewRuleType, newRuleTarget, setNewRuleTarget, newNTracks, setNewNTracks, newIntervalMinutes, setNewIntervalMinutes, newTimes, handleAddRule } = rule;
  return (
  <div className="ra-add-rule">
    <span className="ra-field-label">{t("radioAnnouncements.addRuleTitle")}</span>
    <div className="ra-add-rule-row">
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
      {newRuleType === "fixed_times" && <FixedTimesInput t={t} rule={rule} />}

    <button className="btn btn-primary" style={{ height: "44px" }} onClick={handleAddRule} disabled={newRuleType === "fixed_times" && newTimes.length === 0}>
      <Icon name="add" size={16} /> {t("radioAnnouncements.addRule")}
    </button>
    </div>
  </div>
  );
}
