import { useEffect, type RefObject } from "react";

export function useStallWatchdog(videoRef: RefObject<HTMLVideoElement | null>, lastSeekTimeRef: RefObject<number>) {
  useEffect(() => {
    let lastTime = -1;
    let stallCount = 0;

    const interval = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || video.paused || video.seeking || video.ended || !video.src) {
        lastTime = -1;
        stallCount = 0;
        return;
      }
      if (Date.now() - lastSeekTimeRef.current < 3500) {
        lastTime = video.currentTime;
        stallCount = 0;
        return;
      }

      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        if (Math.abs(video.currentTime - lastTime) < 0.05) {
          stallCount++;
          if (stallCount >= 3) {
            stallCount = 0;
            video.play().catch(() => {});
          }
        } else {
          stallCount = 0;
        }
      }
      lastTime = video.currentTime;
    }, 2500);

    return () => window.clearInterval(interval);
  }, [videoRef, lastSeekTimeRef]);
}
