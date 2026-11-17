"use client";

import React from "react";
import { useRouter } from "next/navigation";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { isSettingsPath, type PlugNoticeState, type UpdateNoticeState } from "./useLayoutNotices";

const DISMISS: React.CSSProperties = { background: "none", border: "none", color: "inherit", cursor: "pointer", padding: "0 0 0 6px", display: "flex", alignItems: "center" };

interface LayoutToastsProps {
  pathname: string;
  update: UpdateNoticeState;
  plug: PlugNoticeState;
}

export default function LayoutToasts({ pathname, update, plug }: LayoutToastsProps) {
  const router = useRouter();
  const { t } = useAppSettings();
  const showUpdate = update.visible && !isSettingsPath(pathname);
  const plugMessage = plug.plugEvent === "added" ? t("storage.pluggedBare") : plug.plugEvent === "abrupt" ? t("storage.abruptBare") : t("storage.unpluggedBare");
  return (
    <>
      {showUpdate && (
        <div className="toast warning clickable olc-press olc-anim-in" style={{ cursor: "pointer", zIndex: 1000 }} onClick={() => router.push("/settings#updates-section")} role="button" tabIndex={0}>
          <Icon name="system_update" size={18} color="var(--accent-text)" />
          <span>{t("settingsPage.updateAvailable")} ({update.version})</span>
          <button
            type="button"
            style={DISMISS}
            onClick={(e) => {
              e.stopPropagation();
              update.dismiss();
            }}
            aria-label={t("common.close")}
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
      {plug.plugEvent && !pathname.startsWith("/storage") && (
        <div
          className={`toast ${plug.plugEvent === "abrupt" ? "error" : "warning"} clickable olc-press olc-anim-in`}
          style={{ cursor: "pointer", zIndex: 1000, bottom: update.visible ? 96 : undefined }}
          onClick={() => { plug.clear(); router.push("/storage"); }}
          role="button"
          tabIndex={0}
          title={t("storage.goTo")}
        >
          <Icon name="usb" size={18} />
          <span>{plugMessage}</span>
        </div>
      )}
    </>
  );
}
