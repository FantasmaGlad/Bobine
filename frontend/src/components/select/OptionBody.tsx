import React from "react";
import Highlight from "@/components/Highlight";
import type { SelectOption } from "./options";

export default function OptionBody({ option, query = "" }: { option: SelectOption; query?: string }) {
  return (
    <>
      {option.thumbnail ? (
        <img className={`sheet-option__thumb${option.square ? " is-square" : ""}`} src={option.thumbnail} alt="" loading="lazy" />
      ) : null}
      <span className="sheet-option__text">
        <span className="sheet-option__label">
          <Highlight text={option.label} query={query} />
        </span>
        {option.sublabel ? (
          <span className="sheet-option__sub">
            <Highlight text={option.sublabel} query={query} />
          </span>
        ) : null}
      </span>
      {option.meta ? <span className="sheet-option__meta">{option.meta}</span> : null}
    </>
  );
}
