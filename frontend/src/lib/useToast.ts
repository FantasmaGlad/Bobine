"use client";

import { useCallback, useEffect, useState } from "react";

export interface ToastState {
  message: string;
  type: "success" | "error" | "warning";
  onClick?: () => void;
}

export type ShowToast = (message: string, type?: ToastState["type"], onClick?: () => void) => void;

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
