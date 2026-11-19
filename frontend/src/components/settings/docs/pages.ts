export const PUBLIC_PAGE_KEYS: { path: string; labelKey: string }[] = [
  { path: "/kiosk", labelKey: "settingsPage.paths.pageKiosk" },
  { path: "/kiosk?channel=network", labelKey: "settingsPage.paths.pageKioskNetwork" },
  { path: "/cinema", labelKey: "settingsPage.paths.pageCinema" },
  { path: "/coach", labelKey: "settingsPage.paths.pageCoach" },
  { path: "/radio?channel=cable", labelKey: "settingsPage.paths.pageRadioCable" },
  { path: "/radio?channel=network", labelKey: "settingsPage.paths.pageRadioNetwork" },
];

export const ANDROID_PAGE_KEYS: { path: string; labelKey: string }[] = [
  { path: "/grid", labelKey: "settingsPage.paths.pageGrid" },
];

export function pagesFor(profile: string) {
  return profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS;
}
