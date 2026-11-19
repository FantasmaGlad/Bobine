"use client";
import React from "react";
import Icon from "@/components/Icon";
import type { ShowToast } from "@/lib/useToast";
import AddRuleForm from "./rules/AddRuleForm";
import RuleRow, { useRuleActions } from "./rules/RuleRow";
import { useNewRule } from "./rules/useNewRule";
import type { Rule } from "./types";

interface RulesPanelProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  rules: Rule[];
  setRules: React.Dispatch<React.SetStateAction<Rule[]>>;
  fetchAll: () => void;
  showToast: ShowToast;
  targetOptions: { value: string; label: string }[];
}

export default function RulesPanel({ t, rules, setRules, fetchAll, showToast, targetOptions }: RulesPanelProps) {
  const newRule = useNewRule(t, showToast, fetchAll);
  const { toggleRuleEnabled, handleDeleteRule } = useRuleActions(t, showToast, setRules);

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
                  <RuleRow key={rule.id} t={t} rule={rule} onToggle={() => toggleRuleEnabled(rule)} onDelete={() => handleDeleteRule(rule.id)} />
                ))}
              </div>
            )}

            <AddRuleForm t={t} rule={newRule} targetOptions={targetOptions} />
          </div>
        </section>
  );
}
