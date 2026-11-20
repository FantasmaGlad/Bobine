import { type ApiError } from "@/lib/apiError";
import { type Capabilities } from "@/lib/devices/types";

export type Notify = (message: string, type?: "success" | "error" | "warning") => void;

export interface SectionProps {
  caps: Capabilities;
  local: boolean;
  refreshKey: number;
  focusId?: string | null;
  focusNonce?: number;
  notify: Notify;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export function errorText(error: ApiError, t: SectionProps["t"]): string {
  const key = `devices.errors.${error.code}`;
  const translated = t(key);
  if (translated !== key) return translated;
  return error.message || t("devices.errors.generic");
}
