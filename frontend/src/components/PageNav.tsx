"use client";

import React from "react";
import SegmentedTabs, { type SegmentedTab } from "@/components/SegmentedTabs";

interface PageNavProps {
  tabs: SegmentedTab[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  actions?: React.ReactNode;
  className?: string;
}

export default function PageNav({ tabs, value, onChange, ariaLabel, actions, className = "" }: PageNavProps) {
  return (
    <div className={`live-block channel-card rl-nav-card page-nav ${className}`.trim()}>
      <div className="channel-card-right page-nav-tabs">
        <SegmentedTabs tabs={tabs} value={value} onChange={onChange} ariaLabel={ariaLabel} />
      </div>
      {actions ? <div className="page-nav-actions">{actions}</div> : null}
    </div>
  );
}
