import { useState } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { errorText, type SectionProps } from "../shared/section";

export interface AckRequest {
  kind: "connect" | "forget" | "power";
  ssid?: string;
  password?: string;
  on?: boolean;
}

export function useWifiActions(notify: SectionProps["notify"], t: SectionProps["t"], reload: () => Promise<void>) {
  const [passwordFor, setPasswordFor] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [ack, setAck] = useState<AckRequest | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (path: string, body: unknown, request: AckRequest, okMessage?: string) => {
    setBusy(true);
    const result = await devicesRequest(path, { body });
    setBusy(false);
    if (result.ok) {
      if (okMessage) notify(okMessage, "success");
      setPasswordFor(null);
      setPassword("");
      setAck(null);
      await reload();
      return;
    }
    if (result.error.code === "ack_required") {
      setAck(request);
      return;
    }
    notify(errorText(result.error, t), "error");
    await reload();
  };

  const connect = (ssid: string, pw?: string, acknowledged = false) =>
    run("/wifi/connect", { ssid, password: pw || undefined, acknowledge_disconnect: acknowledged }, { kind: "connect", ssid, password: pw }, t("devices.wifi.connecting"));
  const forget = (ssid: string, acknowledged = false) =>
    run("/wifi/forget", { ssid, acknowledge_disconnect: acknowledged }, { kind: "forget", ssid }, t("devices.wifi.forgotten"));
  const power = (on: boolean, acknowledged = false) =>
    run("/wifi/power", { on, acknowledge_disconnect: acknowledged }, { kind: "power", on });

  const confirm = async () => {
    const result = await devicesRequest<{ confirmed: boolean }>("/wifi/confirm", { body: {} });
    if (result.ok) {
      notify(t("devices.wifi.confirmed"), "success");
      await reload();
    } else {
      notify(errorText(result.error, t), "error");
    }
  };

  const proceedAfterAck = () => {
    if (!ack) return;
    if (ack.kind === "connect" && ack.ssid) void connect(ack.ssid, ack.password, true);
    else if (ack.kind === "forget" && ack.ssid) void forget(ack.ssid, true);
    else if (ack.kind === "power") void power(ack.on === true, true);
  };

  return {
    passwordFor, setPasswordFor, password, setPassword, ack, setAck, busy,
    connect, forget, power, confirm, proceedAfterAck,
  };
}

export type WifiActions = ReturnType<typeof useWifiActions>;
