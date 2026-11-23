import { buildOutputUrl } from "@/lib/displayChannel";
import { OUTPUTS, type OutputId } from "@/lib/outputs";

export interface PageKey {
  path: string;
  labelKey: string;
  output?: OutputId;
}

export const PUBLIC_PAGE_KEYS: PageKey[] = [
  { path: "/kiosk", labelKey: "settingsPage.paths.pageKiosk" },
  ...OUTPUTS.filter((output) => !output.wired).map((output) => ({
    path: buildOutputUrl("kiosk", "", output.id), labelKey: "settingsPage.paths.pageKioskNetwork", output: output.id,
  })),
  { path: "/cinema", labelKey: "settingsPage.paths.pageCinema" },
  { path: "/coach", labelKey: "settingsPage.paths.pageCoach" },
  ...OUTPUTS.map((output) => ({ path: buildOutputUrl("radio", "", output.id), labelKey: "settingsPage.paths.pageRadio", output: output.id })),
];

export const ANDROID_PAGE_KEYS: PageKey[] = [
  { path: "/grid", labelKey: "settingsPage.paths.pageGrid" },
];

export function pagesFor(profile: string) {
  return profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS;
}
