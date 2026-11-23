import { screenUrl } from "@/lib/displayChannel";
import { OUTPUTS, type OutputId } from "@/lib/outputs";

export interface PageKey {
  path: string;
  labelKey: string;
  output?: OutputId;
}

export const PUBLIC_PAGE_KEYS: PageKey[] = [
  ...OUTPUTS.map((output) => ({ path: screenUrl(output.id), labelKey: "settingsPage.paths.pageScreen", output: output.id })),
  { path: "/coach", labelKey: "settingsPage.paths.pageCoach" },
];

export const ANDROID_PAGE_KEYS: PageKey[] = [
  { path: "/grid", labelKey: "settingsPage.paths.pageGrid" },
];

export function pagesFor(profile: string) {
  return profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS;
}
