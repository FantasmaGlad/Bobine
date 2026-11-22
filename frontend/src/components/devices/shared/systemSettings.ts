import { devicesRequest } from "@/lib/devices/request";
import { errorText, type Notify, type SectionProps } from "./section";

export async function openSystemSettings(target: "bluetooth" | "sound", notify: Notify, t: SectionProps["t"]) {
  const result = await devicesRequest<{ ok: boolean }>("/system-settings", { body: { target } });
  if (result.ok) notify(t("devices.settingsOpened"), "success");
  else notify(errorText(result.error, t), "error");
}
