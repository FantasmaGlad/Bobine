"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

function isLocalScreen() {
  return typeof window !== "undefined" && (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost");
}

export function useCoachNavigation(isCoachMode: boolean, stop: () => Promise<unknown> | unknown) {
  const router = useRouter();

  const handleBackFromPicker = () => {
    router.push(isLocalScreen() ? "/grid" : "/");
  };

  const handleExitCoach = async () => {
    try {
      await stop();
    } finally {
      handleBackFromPicker();
    }
  };

  const wasCoachModeRef = useRef(isCoachMode);
  useEffect(() => {
    if (wasCoachModeRef.current && !isCoachMode && isLocalScreen()) {
      router.replace("/grid");
    }
    wasCoachModeRef.current = isCoachMode;
  }, [isCoachMode, router]);

  return { handleExitCoach, handleBackFromPicker };
}
