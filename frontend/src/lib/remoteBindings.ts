import { ANALOG_TRIGGERS, DEFAULT_REMOTE_BINDINGS, GAMEPAD_DIRECTIONS, REMOTE_ACTIONS } from "./remoteBindings.generated.ts";

export { ANALOG_TRIGGERS, DEFAULT_REMOTE_BINDINGS, GAMEPAD_DIRECTIONS, REMOTE_ACTIONS };

export type RemoteAction = (typeof REMOTE_ACTIONS)[number];

export type RemoteBindings = Readonly<Record<string, readonly RemoteAction[]>>;

export type RemoteActionHandlers = Partial<Record<RemoteAction, () => void>>;

export function keyBinding(bindings: RemoteBindings, key: string, keyCode: number): readonly RemoteAction[] | undefined {
  return bindings[`key:${key}`] ?? bindings[`code:${keyCode}`];
}

export function gamepadBindings(bindings: RemoteBindings): [number, readonly RemoteAction[]][] {
  return Object.entries(bindings)
    .filter(([input]) => input.startsWith("pad:"))
    .map(([input, actions]) => [Number(input.slice(4)), actions]);
}

export function pickHandler(handlers: RemoteActionHandlers, actions: readonly RemoteAction[] | undefined): (() => void) | undefined {
  for (const action of actions ?? []) {
    const handler = handlers[action];
    if (handler) return handler;
  }
  return undefined;
}

export function parseRemoteBindings(raw: unknown): RemoteBindings | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const known = new Set<string>(REMOTE_ACTIONS);
  const entries = Object.entries(raw as Record<string, unknown>).filter(
    (entry): entry is [string, RemoteAction[]] =>
      Array.isArray(entry[1]) && entry[1].every((action) => typeof action === "string" && known.has(action)),
  );
  return Object.fromEntries(entries);
}
