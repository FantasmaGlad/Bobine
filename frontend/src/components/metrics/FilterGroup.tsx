"use client";

import React from "react";
import Icon from "@/components/Icon";
import ScrollNav from "@/components/ScrollNav";

export interface FilterChoice<T extends string> {
  value: T;
  label: string;
  icon?: string;
}

interface FilterGroupProps<T extends string> {
  icon: string;
  label: string;
  value: T;
  choices: FilterChoice<T>[];
  onChange: (value: T) => void;
}

export default function FilterGroup<T extends string>({ icon, label, value, choices, onChange }: FilterGroupProps<T>) {
  return (
    <div className="metrics-filter-group">
      <span className="metrics-filter-label">
        <Icon name={icon} size={16} /> {label} :
      </span>
      <ScrollNav>
        {choices.map((choice) => (
          <button key={choice.value} type="button" className={`view-btn ${value === choice.value ? "active" : ""}`} onClick={() => onChange(choice.value)}>
            {choice.icon ? <><Icon name={choice.icon} size={14} /> {choice.label}</> : choice.label}
          </button>
        ))}
      </ScrollNav>
    </div>
  );
}
