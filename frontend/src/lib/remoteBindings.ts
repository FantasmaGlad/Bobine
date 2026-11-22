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
