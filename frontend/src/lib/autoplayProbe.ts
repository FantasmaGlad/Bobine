export function detectAutoplayAllowed(timeoutMs = 600): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") {
      resolve(false);
      return;
    }
    const AudioContextClass =
      window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) {
      resolve(false);
      return;
    }
    let ctx: AudioContext;
    try {
      ctx = new AudioContextClass();
    } catch {
      resolve(false);
      return;
    }
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
