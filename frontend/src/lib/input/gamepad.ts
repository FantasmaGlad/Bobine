import { ANALOG_TRIGGERS, GAMEPAD_DIRECTIONS, gamepadBindings, pickHandler, type RemoteActionHandlers } from "../remoteBindings.ts";
import { currentRemoteBindings } from "../remoteBindingsStore.ts";
import { ButtonRepeat } from "./repeat.ts";

const AXIS_THRESHOLD = 0.5;

function axisButtons(axes: readonly number[]): Record<number, boolean> {
  return {
    12: axes[1] !== undefined && axes[1] < -AXIS_THRESHOLD,
    13: axes[1] !== undefined && axes[1] > AXIS_THRESHOLD,
    14: axes[0] !== undefined && axes[0] < -AXIS_THRESHOLD,
    15: axes[0] !== undefined && axes[0] > AXIS_THRESHOLD,
  };
}

function isPressed(gp: Gamepad, button: number, axes: Record<number, boolean>): boolean {
  const analog = (ANALOG_TRIGGERS as readonly number[]).includes(button) && (gp.buttons[button]?.value ?? 0) > 0.5;
  return (gp.buttons[button]?.pressed ?? false) || analog || (axes[button] ?? false);
}

export function listenGamepads(handlers: () => RemoteActionHandlers): () => void {
  let rafId: number | null = null;
  const repeat = new ButtonRepeat();

  const poll = () => {
    let polling = false;
    if (typeof navigator !== "undefined" && typeof navigator.getGamepads === "function") {
      const gamepads = navigator.getGamepads();
      const now = Date.now();
      const h = handlers();
      for (let i = 0; i < gamepads.length; i++) {
        const gp = gamepads[i];
        if (!gp || !gp.connected) continue;
        polling = true;
        const axes = axisButtons(gp.axes);
        for (const [button, actions] of gamepadBindings(currentRemoteBindings())) {
          const action = pickHandler(h, actions);
          if (!action) continue;
          if (repeat.fires(`gp_${i}_${button}`, isPressed(gp, button, axes), button in GAMEPAD_DIRECTIONS, now)) action();
        }
      }
    }
    rafId = polling ? requestAnimationFrame(poll) : null;
  };

  const start = () => {
    if (rafId === null) rafId = requestAnimationFrame(poll);
  };
  window.addEventListener("gamepadconnected", start);
  start();
  return () => {
    window.removeEventListener("gamepadconnected", start);
    if (rafId !== null) cancelAnimationFrame(rafId);
  };
}
