import React from "react";
import Icon from "@/components/Icon";
import OptionBody from "./OptionBody";
import { groupOptions, type SelectOption } from "./options";

interface OptionRowsProps {
  listId: string;
  value: string;
  visible: SelectOption[];
  query: string;
  placeholder?: string;
  hasEmptyEntry: boolean;
  activeIndex: number;
  emptyLabel: string;
  onActivate: (index: number) => void;
  onChoose: (value: string) => void;
}

function rowClass(selected: boolean, active: boolean): string {
  return `sheet-option olc-press${selected ? " is-selected" : ""}${active ? " is-active" : ""}`;
}

export default function OptionRows({ listId, value, visible, query, placeholder, hasEmptyEntry, activeIndex, emptyLabel, onActivate, onChoose }: OptionRowsProps) {
  let rowCounter = hasEmptyEntry ? 1 : 0;
  return (
    <>
      {hasEmptyEntry && (
        <button
          type="button"
          role="option"
          aria-selected={value === ""}
          data-row={0}
          id={`${listId}-0`}
          className={rowClass(value === "", activeIndex === 0)}
          onMouseEnter={() => onActivate(0)}
          onClick={() => onChoose("")}
        >
          <span className="sheet-option__text">
            <span className="sheet-option__label is-placeholder">{placeholder}</span>
          </span>
          {value === "" && <Icon name="check" size={18} />}
        </button>
      )}
      {visible.length === 0 ? (
        <p className="live-empty">{emptyLabel}</p>
      ) : (
        groupOptions(visible).map(([group, items]) => (
          <div key={group} className="sheet-group">
            {group ? <div className="sheet-group__title">{group}</div> : null}
            {items.map((option) => {
              const index = rowCounter++;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="option"
                  aria-selected={option.value === value}
                  data-row={index}
                  id={`${listId}-${index}`}
                  className={rowClass(option.value === value, activeIndex === index)}
                  onMouseEnter={() => onActivate(index)}
                  onClick={() => onChoose(option.value)}
                >
                  <OptionBody option={option} query={query} />
                  {option.value === value && <Icon name="check" size={18} />}
                </button>
              );
            })}
          </div>
        ))
      )}
    </>
  );
}
