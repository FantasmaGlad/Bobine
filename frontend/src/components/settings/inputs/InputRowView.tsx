"use client";

import type { InputRow } from "@/lib/inputSource";
import { PAD_BUTTONS } from "@/lib/inputSource";
import type { RemoteAction } from "@/lib/remoteBindings";

type Translate = (key: string, params?: Record<string, string | number>) => string;

export function inputLabel(row: Pick<InputRow, "kind" | "value">, t: Translate): string {
  if (row.kind === "code") return t("settingsPage.inputs.codeLabel", { value: row.value });
  if (row.kind === "pad") {
    const name = PAD_BUTTONS[Number(row.value)] ?? row.value;
    const known = `settingsPage.inputs.pad.${name}`;
    const label = t(known);
    return t("settingsPage.inputs.padLabel", { value: label === known ? name : label });
  }
  const known = `settingsPage.inputs.keys.${row.value}`;
  const label = row.value.includes(".") ? known : t(known);
  return label === known ? row.value : label;
}

export default function InputRowView({ row, actions, t, onBind }: {
  row: InputRow;
  actions: readonly RemoteAction[];
  t: Translate;
  onBind: (actions: RemoteAction[] | null) => void;
}) {
  const [primary, ...fallbacks] = row.actions;
  return (
    <li id={`input-${row.source}`} className={`inputs-row${row.disabled ? " is-disabled" : ""}`}>
      <span className="inputs-row__name">{inputLabel(row, t)}</span>
      <select
        className="inputs-row__action"
        aria-label={inputLabel(row, t)}
        value={primary ?? ""}
        onChange={(event) => onBind(event.target.value ? [event.target.value as RemoteAction, ...fallbacks.filter((action) => action !== event.target.value)] : [])}
      >
        <option value="">{t("settingsPage.inputs.disabled")}</option>
        {actions.map((action) => <option key={action} value={action}>{t(`settingsPage.inputs.actions.${action}`)}</option>)}
      </select>
      <span className="inputs-row__note">
        {fallbacks.length > 0 && t("settingsPage.inputs.fallback", { actions: fallbacks.map((action) => t(`settingsPage.inputs.actions.${action}`)).join(", ") })}
        {row.custom && <em>{t("settingsPage.inputs.custom")}</em>}
      </span>
      <span className="inputs-row__buttons">
        {!row.disabled && <button type="button" className="btn btn-secondary btn-sm" onClick={() => onBind([])}>{t("settingsPage.inputs.disable")}</button>}
        {row.custom && <button type="button" className="btn btn-secondary btn-sm" onClick={() => onBind(null)}>{t("settingsPage.inputs.restore")}</button>}
      </span>
    </li>
  );
}
