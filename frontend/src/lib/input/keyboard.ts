import { keyBinding, pickHandler, type RemoteActionHandlers } from "../remoteBindings.ts";
import { currentRemoteBindings } from "../remoteBindingsStore.ts";

function isTextTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return Boolean(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable));
}

export function listenKeyboard(handlers: () => RemoteActionHandlers): () => void {
  const onKeyDown = (e: KeyboardEvent) => {
    if (isTextTarget(e.target)) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const action = pickHandler(handlers(), keyBinding(currentRemoteBindings(), e.key, e.keyCode));
    if (action) {
      e.preventDefault();
      action();
    }
  };
  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}
