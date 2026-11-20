import { useEffect } from "react";

export function useFocusFlash(focusId: string | null | undefined, nonce: number | undefined, ready: boolean) {
  useEffect(() => {
    if (!focusId || !ready) return;
    const frame = requestAnimationFrame(() => {
      const el = Array.from(document.querySelectorAll<HTMLElement>("[data-focus-id]")).find((node) => node.dataset.focusId === focusId);
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      el.classList.add("dv-flash");
      setTimeout(() => el.classList.remove("dv-flash"), 2200);
    });
    return () => cancelAnimationFrame(frame);
  }, [focusId, nonce, ready]);
}
