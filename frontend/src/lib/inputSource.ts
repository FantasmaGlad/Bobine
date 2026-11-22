import type { RemoteAction, RemoteBindings } from "./remoteBindings.ts";

export type InputKind = "key" | "code" | "pad";

export interface InputRow {
  source: string;
  kind: InputKind;
  value: string;
  actions: readonly RemoteAction[];
  custom: boolean;
  disabled: boolean;
}

export const PAD_BUTTONS: Readonly<Record<number, string>> = {
  0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "LT", 7: "RT", 8: "Select", 9: "Start",
  10: "L3", 11: "R3", 12: "up", 13: "down", 14: "left", 15: "right", 16: "home",
};

export function sourceFromKey(key: string, keyCode: number): string {
  return key && key !== "Unidentified" ? `key:${key}` : `code:${keyCode}`;
}

export function pressedButton(previous: readonly boolean[], current: readonly boolean[]): number | null {
  const index = current.findIndex((pressed, button) => pressed && !previous[button]);
  return index >= 0 && index <= 19 ? index : null;
}

export function splitSource(source: string): { kind: InputKind; value: string } {
  const at = source.indexOf(":");
  return { kind: source.slice(0, at) as InputKind, value: source.slice(at + 1) };
}

const ORDER: Record<InputKind, number> = { key: 0, code: 1, pad: 2 };

export function inputRows(bindings: RemoteBindings, overrides: RemoteBindings): InputRow[] {
  const sources = new Set([...Object.keys(bindings), ...Object.keys(overrides)]);
  return [...sources]
    .map((source) => {
      const actions = overrides[source] ?? bindings[source] ?? [];
      return { source, ...splitSource(source), actions, custom: source in overrides, disabled: actions.length === 0 };
    })
    .sort((a, b) => ORDER[a.kind] - ORDER[b.kind] || a.value.localeCompare(b.value, undefined, { numeric: true }));
}
