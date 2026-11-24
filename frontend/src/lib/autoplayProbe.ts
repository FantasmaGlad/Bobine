import { createPlaybackAudioContext } from "./audio/context";

export function detectAutoplayAllowed(timeoutMs = 600): Promise<boolean> {
  return new Promise((resolve) => {
    const created = createPlaybackAudioContext();
    if (!created) {
      resolve(false);
      return;
    }
    const ctx = created;
    let done = false;
    const finish = (allowed: boolean) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      ctx.removeEventListener("statechange", onStateChange);
      ctx.close().catch(() => {});
      resolve(allowed);
    };
    const onStateChange = () => {
      if (ctx.state === "running") finish(true);
    };
    const timer = setTimeout(() => finish(ctx.state === "running"), timeoutMs);
    ctx.addEventListener("statechange", onStateChange);
    if (ctx.state === "running") {
      finish(true);
      return;
    }
    ctx.resume().then(onStateChange).catch(() => {});
  });
}
