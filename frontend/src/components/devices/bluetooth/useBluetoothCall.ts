import { useEffect, useState } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { errorText, type SectionProps } from "../shared/section";

export type BluetoothCall = (path: string, body?: unknown, okMessage?: string) => Promise<void>;

export function useDiscoveryPolling(discovering: boolean, reload: () => Promise<void>) {
  useEffect(() => {
    if (!discovering) return;
    const timer = setInterval(() => { void reload(); }, 3000);
    return () => clearInterval(timer);
  }, [discovering, reload]);
}

export function useBluetoothCall(notify: SectionProps["notify"], t: SectionProps["t"], reload: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const call: BluetoothCall = async (path, body, okMessage) => {
    setBusy(true);
    const result = await devicesRequest(path, { method: "POST", body: body ?? {} });
    setBusy(false);
    if (result.ok) {
      if (okMessage) notify(okMessage, "success");
      await reload();
    } else {
      notify(errorText(result.error, t), "error");
      await reload();
    }
  };
  return { busy, call };
}
