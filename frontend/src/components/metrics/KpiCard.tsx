"use client";

import React from "react";
import Icon from "@/components/Icon";

interface KpiCardProps {
  title: string;
  icon: string;
  filled?: boolean;
  value: React.ReactNode;
  unit: string;
  detail: string;
  children?: React.ReactNode;
}

export default function KpiCard({ title, icon, filled, value, unit, detail, children }: KpiCardProps) {
  return (
    <div className="metrics-kpi-card">
      <div className="metrics-kpi-header">
        <span className="metrics-kpi-title">{title}</span>
        <div className="metrics-kpi-icon-wrap" style={{ color: "var(--accent-text)" }}>
          <Icon name={icon} size={24} filled={filled} />
        </div>
      </div>
      <div className="metrics-kpi-value-row">
        <span className="metrics-kpi-main-num">{value}</span>
        <span className="metrics-kpi-unit">{unit}</span>
      </div>
      <p className="metrics-kpi-detail">{detail}</p>
      {children}
    </div>
  );
}
