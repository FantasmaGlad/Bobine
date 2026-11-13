export function seekWhenReady(el: HTMLMediaElement, targetSeconds: number, onDone?: () => void) {
  const apply = () => {
    try {
      const wasPlaying = !el.paused;
      if (wasPlaying) el.pause();
      el.currentTime = targetSeconds;
      if (!wasPlaying) {
        onDone?.();
        return;
      }
      el.addEventListener("seeked", () => {
        el.play().catch(() => {});
        onDone?.();
      }, { once: true });
    } catch {
    }
  };
  if (el.readyState >= HTMLMediaElement.HAVE_METADATA) apply();
  else el.addEventListener("loadedmetadata", apply, { once: true });
}
