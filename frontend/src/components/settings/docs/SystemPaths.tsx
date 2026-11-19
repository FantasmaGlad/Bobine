"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { SettingsData } from "../types";

const PATH_LABEL_KEYS: Record<string, string> = {
  database_url: "settingsPage.paths.database_url",
  media_dir: "settingsPage.paths.media_dir",
  watch_dir: "settingsPage.paths.watch_dir",
  thumbnails_dir: "settingsPage.paths.thumbnails_dir",
  backgrounds_dir: "settingsPage.paths.backgrounds_dir",
  backgrounds_watch_dir: "settingsPage.paths.backgrounds_watch_dir",
  audio_dir: "settingsPage.paths.audio_dir",
  audio_watch_dir: "settingsPage.paths.audio_watch_dir",
  radio_dir: "settingsPage.paths.radio_dir",
  radio_watch_dir: "settingsPage.paths.radio_watch_dir",
  radio_covers_dir: "settingsPage.paths.radio_covers_dir",
  radio_announcements_dir: "settingsPage.paths.radio_announcements_dir",
  branding_dir: "settingsPage.paths.branding_dir",
  logs_dir: "settingsPage.paths.logs_dir",
  subtitles_dir: "settingsPage.paths.subtitles_dir",
};

const ACTION_STYLE = { height: "30px", padding: "0 10px", fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "4px" } as const;

function PathRow({ name, value, onCopy, onOpen }: { name: string; value: string; onCopy: (path: string) => void; onOpen: (path: string) => void }) {
  const { t } = useAppSettings();
  const cleanPath = value.replace(/^sqlite:\/\/\//, "");
  return (
    <div className="settings-path-row settings-path-row--system">
      <span className="settings-path-key">{t(PATH_LABEL_KEYS[name] || name)}</span>
      <span className="settings-path-val settings-path-val--path" title={value}>
        {value}
      </span>
      <div className="settings-path-actions">
        <button type="button" className="btn btn-secondary olc-press" style={ACTION_STYLE} onClick={() => onCopy(cleanPath)} title={t("settingsPage.paths.copyPath")}>
          <Icon name="content_copy" size={14} />
          <span>{t("settingsPage.paths.copyPath")}</span>
        </button>
        <button type="button" className="btn btn-secondary olc-press" style={ACTION_STYLE} onClick={() => onOpen(cleanPath)} title={t("settingsPage.paths.openFolder")}>
          <Icon name="folder_open" size={14} />
          <span>{t("settingsPage.paths.openFolder")}</span>
        </button>
      </div>
    </div>
  );
}

export default function SystemPaths({ data, open, onCopy, onOpen }: {
  data: SettingsData; open: boolean; onCopy: (path: string) => void; onOpen: (path: string) => void;
}) {
  const { t } = useAppSettings();
  return (
    <details className="settings-doc-group" open={open}>
      <summary className="settings-doc-header">
        <Icon name="folder" size={18} />
        <span>{t("settingsPage.paths.systemHeading")}</span>
      </summary>
      <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.systemHint")}</p>
      <div style={{ margin: "8px 0 14px", padding: "10px 14px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--accent-primary) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--accent-primary) 28%, transparent)", display: "flex", alignItems: "center", gap: "10px" }}>
            <Icon name="smartphone" size={18} color="var(--accent-text)" />
            <span style={{ fontSize: "0.85rem", lineHeight: 1.45, color: "var(--text-main)" }}>
              {t("settingsPage.paths.androidStorageNote")}
            </span>
          </div>
      <div className="settings-paths">
        {Object.entries(data.paths).map(([key, value]) => (
          <PathRow key={key} name={key} value={value} onCopy={onCopy} onOpen={onOpen} />
        ))}
      </div>
    </details>
  );
}
