import { useEffect, type RefObject } from "react";

export function useAudioContextKeepAlive(audioCtxRef: RefObject<AudioContext | null>, unlockedRef: RefObject<boolean>) {
  useEffect(() => {
    const resumeIfSuspended = () => {
      const ctx = audioCtxRef.current;
      if (ctx && unlockedRef.current && ctx.state !== "running") ctx.resume().catch(() => {});
    };
    document.addEventListener("visibilitychange", resumeIfSuspended);
    const id = setInterval(resumeIfSuspended, 5000);
    return () => {
      document.removeEventListener("visibilitychange", resumeIfSuspended);
      clearInterval(id);
    };
  }, [audioCtxRef, unlockedRef]);
}
