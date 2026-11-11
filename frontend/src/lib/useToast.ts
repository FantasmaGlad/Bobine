"use client";

import { useCallback, useEffect, useState } from "react";

export interface ToastState {
  message: string;
  type: "success" | "error" | "warning";
  /** Action au clic sur le message (ex. ouvrir la section concernée). */
  onClick?: () => void;
}

export type ShowToast = (message: string, type?: ToastState["type"], onClick?: () => void) => void;

/** Message éphémère d'une page : affiché par `showToast`, effacé seul après `durationMs`. */
export function useToast(durationMs = 4000) {
  const [toast, setToast] = useState<ToastState | null>(null);

  const showToast: ShowToast = useCallback((message, type = "success", onClick) => setToast({ message, type, onClick }), []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), durationMs);
    return () => clearTimeout(timer);
  }, [toast, durationMs]);

  return { toast, showToast, setToast };
}
