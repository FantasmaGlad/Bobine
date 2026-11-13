"use client";
import React from "react";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { formatTime, formatWallClock } from "@/lib/format";

interface GridStandbyProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  now: Date;
  nowPlaying: { title?: string | null; video_id?: number | null; position_seconds: number; duration_seconds: number; playing: boolean } | null;
  themeFg: string;
  onSwitchToDual: () => void;
}

export default function GridStandby({ t, now, nowPlaying, themeFg, onSwitchToDual }: GridStandbyProps) {
  return (
      <div className="grid-standby-root">
        <div className="grid-standby-card">
          <div className="grid-standby-header">
            <AppLogo size={48} className="grid-standby-logo" />
            <span className="grid-standby-clock">{formatWallClock(now)}</span>
          </div>

          <div className="grid-standby-content">
            <h1 className="grid-standby-title">{t("settingsPage.gridStandbyTitle")}</h1>
            <p className="grid-standby-subtitle">{t("settingsPage.gridStandbySubtitle")}</p>

            <div className="grid-standby-status-box">
              <div className="grid-standby-status-badge">
                <span className="grid-standby-pulse-dot" />
                <Icon name="tv" size={20} />
                <span>{t("settingsPage.gridStandbyHdmiActive")}</span>
              </div>
              <p className="grid-standby-status-desc">{t("settingsPage.gridStandbyHdmiHelp")}</p>
              {nowPlaying && (
                <div className="grid-standby-now-playing">
                  <span className="grid-standby-now-playing-label">{t("cinema.nowPlaying")} :</span>
                  <strong className="grid-standby-now-playing-title">{nowPlaying.title}</strong>
                  {nowPlaying.duration_seconds ? (
                    <span className="grid-standby-now-playing-time">
                      ({formatTime(nowPlaying.position_seconds)} / {formatTime(nowPlaying.duration_seconds)})
                    </span>
                  ) : null}
                </div>
              )}
            </div>

            <div className="grid-standby-actions">
              <button
                type="button"
                className="btn btn-primary grid-standby-btn-main"
                style={{ color: themeFg }}
                onClick={onSwitchToDual}
              >
                <Icon name="devices" size={22} color={themeFg} />
                <span>{t("settingsPage.gridStandbySwitchToDual")}</span>
              </button>
              <p className="grid-standby-action-hint">{t("settingsPage.gridStandbySwitchToDualHelp")}</p>

              <a
                href="/"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary grid-standby-btn-admin"
              >
                <Icon name="settings" size={18} />
                <span>{t("settingsPage.gridStandbyOpenAdmin")}</span>
              </a>
            </div>
          </div>
        </div>
      </div>
  );
}
