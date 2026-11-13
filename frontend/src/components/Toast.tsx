"use client";

import Icon from "@/components/Icon";
import type { ToastState } from "@/lib/useToast";

export default function Toast({ toast }: { toast: ToastState | null }) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.type}`}>
      {toast.type === "success" && <Icon name="check_circle" size={20} color="var(--accent-success-text)" filled />}
      {toast.type === "error" && <Icon name="error" size={20} color="var(--accent-error-text)" filled />}
      <span>{toast.message}</span>
    </div>
  );
}
