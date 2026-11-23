import { OUTPUTS, type OutputId } from "./outputs.ts";

export interface NavLinkConfig {
  href: string;
  labelKey: string;
  iconName: string;
  advanced?: boolean;
}

export interface NavGroupConfig {
  groupKey: string;
  iconName: string;
  children: NavLinkConfig[];
  advanced?: boolean;
}

export type NavEntry = NavLinkConfig | NavGroupConfig;

export function isNavGroup(entry: NavEntry): entry is NavGroupConfig {
  return (entry as NavGroupConfig).children !== undefined;
}

export function dashboardHref(id: OutputId): string {
  return `/dashboard-${id.replace("_", "-")}`;
}

export const navEntries: NavEntry[] = [
  ...OUTPUTS.map((output) => ({
    href: dashboardHref(output.id),
    labelKey: `nav.dashboardOutputs.${output.id}`,
    iconName: output.wired ? "cable" : "wifi",
  })),
  {
    groupKey: "nav.libraryGroup",
    iconName: "video_library",
    children: [
      { href: "/library", labelKey: "nav.libraryCourses", iconName: "video_library" },
      { href: "/library/coach", labelKey: "nav.libraryCoach", iconName: "fitness_center", advanced: true },
      { href: "/library/radio", labelKey: "nav.libraryRadio", iconName: "album" },
      { href: "/library/reminders", labelKey: "nav.libraryReminders", iconName: "campaign" },
      { href: "/library/visuals", labelKey: "nav.libraryVisuals", iconName: "slideshow" },
    ],
  },
  { href: "/schedule", labelKey: "nav.schedule", iconName: "calendar_month" },
  {
    groupKey: "nav.metricsGroup",
    iconName: "analytics",
    advanced: true,
    children: [
      { href: "/metrics/courses", labelKey: "nav.metricsCourses", iconName: "school" },
      { href: "/metrics/system", labelKey: "nav.metricsSystem", iconName: "monitor_heart" },
    ],
  },
];

export const footerNavLinks: NavLinkConfig[] = [
  { href: "/devices", labelKey: "nav.devices", iconName: "devices" },
  { href: "/storage", labelKey: "nav.storage", iconName: "usb" },
  { href: "/settings", labelKey: "nav.settings", iconName: "settings" },
  { href: "/logs", labelKey: "nav.logs", iconName: "receipt_long", advanced: true },
];

export const navLinks: NavLinkConfig[] = navEntries.flatMap((entry) =>
  isNavGroup(entry) ? entry.children : [entry],
);

export function visibleNavEntries(simplified: boolean): NavEntry[] {
  if (!simplified) return navEntries;
  return navEntries
    .filter((entry) => !entry.advanced)
    .map((entry) => (isNavGroup(entry) ? { ...entry, children: entry.children.filter((child) => !child.advanced) } : entry));
}

export function visibleFooterLinks(simplified: boolean): NavLinkConfig[] {
  return simplified ? footerNavLinks.filter((link) => !link.advanced) : footerNavLinks;
}
