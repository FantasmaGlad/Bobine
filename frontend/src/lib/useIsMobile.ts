"use client";

import { useEffect, useState } from "react";

export function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint}px)`);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lit l'état initial d'un système externe (matchMedia) avant que le listener de changement ne prenne le relais ; nécessaire pour un rendu correct dès le premier affichage côté client
    setIsMobile(mql.matches);
    const listener = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mql.addEventListener("change", listener);
    return () => mql.removeEventListener("change", listener);
  }, [breakpoint]);

  return isMobile;
}
