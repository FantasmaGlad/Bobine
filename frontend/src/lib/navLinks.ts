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

export const navEntries: NavEntry[] = [
  { href: "/dashboard-cable", labelKey: "nav.dashboardCable", iconName: "cable" },
  { href: "/dashboard-network", labelKey: "nav.dashboardNetwork", iconName: "wifi" },
  {
    groupKey: "nav.radioGroup",
    iconName: "radio",
    children: [
      { href: "/radio-remote", labelKey: "nav.radioRemote", iconName: "graphic_eq" },
      { href: "/radio-library", labelKey: "nav.radioLibrary", iconName: "album" },
      { href: "/radio-announcements", labelKey: "nav.radioAnnouncements", iconName: "campaign" },
    ],
  },
  {
    groupKey: "nav.coachGroup",
    iconName: "fitness_center",
    advanced: true,
    children: [
      { href: "/audio", labelKey: "nav.audio", iconName: "library_music" },
      { href: "/backgrounds", labelKey: "nav.backgrounds", iconName: "gradient" },
    ],
  },
  { href: "/library", labelKey: "nav.library", iconName: "video_library" },
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
  return simplified ? navEntries.filter((entry) => !entry.advanced) : navEntries;
}

export function visibleFooterLinks(simplified: boolean): NavLinkConfig[] {
  return simplified ? footerNavLinks.filter((link) => !link.advanced) : footerNavLinks;
}
