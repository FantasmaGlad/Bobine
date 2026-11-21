"use client";

import AppLogo from "@/components/AppLogo";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatWallClock } from "@/lib/format";
import { useTicker } from "./useCinemaVideos";

function WallClock({ className }: { className: string }) {
  const now = useTicker(1000);
  return <span className={className} suppressHydrationWarning>{formatWallClock(new Date(now))}</span>;
}

export function EmptyScreen() {
  const { t } = useAppSettings();
  return (
    <div className="cinema-empty-screen">
      <AppLogo className="cinema-empty-logo" />
      <WallClock className="cinema-empty-clock" />
      <span className="cinema-empty-message">{t("cinema.empty")}</span>
    </div>
  );
}

export function StandbyScreen() {
  const { t } = useAppSettings();
  return (
    <div className="cinema-standby-screen">
      <AppLogo size={96} className="cinema-standby-logo" />
      <WallClock className="cinema-standby-clock" />
      <h1 className="cinema-standby-title">{t("cinema.standbyTitle")}</h1>
      <p className="cinema-standby-hint">{t("cinema.standbyHint")}</p>
    </div>
  );
}
