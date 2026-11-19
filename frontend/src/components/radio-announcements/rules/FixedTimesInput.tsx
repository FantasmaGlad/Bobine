"use client";

import Icon from "@/components/Icon";
import type { useNewRule } from "./useNewRule";

export default function FixedTimesInput({ t, rule }: { t: (key: string) => string; rule: ReturnType<typeof useNewRule> }) {
  const { newTimes, newTimeInput, setNewTimeInput, addTime, removeTime } = rule;
  return (
  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
    <div style={{ display: "flex", gap: "8px" }}>
      <input type="time" className="form-control" value={newTimeInput} onChange={(e) => setNewTimeInput(e.target.value)} style={{ flex: 1 }} />
      <button className="btn btn-secondary" onClick={addTime}>
        <Icon name="add" size={16} /> {t("radioAnnouncements.addTime")}
      </button>
    </div>
    {newTimes.length === 0 ? (
      <span className="live-empty">{t("radioAnnouncements.noTimes")}</span>
    ) : (
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
        {newTimes.map((tm) => (
          <span key={tm} className="ra-time-pill" onClick={() => removeTime(tm)} title={t("radioAnnouncements.deleteRule")}>
            {tm} <Icon name="close" size={12} />
          </span>
        ))}
      </div>
    )}
  </div>
  );
}
