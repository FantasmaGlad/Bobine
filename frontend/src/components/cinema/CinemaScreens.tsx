"use client";

import AppLogo from "@/components/AppLogo";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatWallClock } from "@/lib/format";

export function EmptyScreen({ now }: { now: Date }) {
  const { t } = useAppSettings();
  return (
    <div className="cinema-empty-screen">
      <AppLogo className="cinema-empty-logo" />
      <span className="cinema-empty-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
      <span className="cinema-empty-message">{t("cinema.empty")}</span>
    </div>
  );
}

export function StandbyScreen({ now }: { now: Date }) {
  const { t } = useAppSettings();
  return (
    <div className="cinema-standby-screen">
      <AppLogo size={96} className="cinema-standby-logo" />
      <span className="cinema-standby-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
      <h1 className="cinema-standby-title">{t("cinema.standbyTitle")}</h1>
      <p className="cinema-standby-hint">{t("cinema.standbyHint")}</p>
    </div>
  );
}
