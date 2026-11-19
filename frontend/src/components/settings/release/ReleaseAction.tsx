"use client";

import Icon from "@/components/Icon";
import { formatBinarySize } from "@/lib/format";
import type { UpdateInfo } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export default function ReleaseAction({ t, updateInfo, applyingUpdate, handleApplyUpdate }: {
  t: Translate; updateInfo: UpdateInfo; applyingUpdate: boolean; handleApplyUpdate: () => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "4px" }}>
      {updateInfo.can_auto_apply ? (
        <button
          type="button"
          className="btn btn-primary"
          style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px" }}
          onClick={handleApplyUpdate}
          disabled={applyingUpdate}
        >
          {applyingUpdate ? (
            <>
              <Icon name="sync" size={16} className="olc-spin" />
              {t("settingsPage.applyingUpdate")}
            </>
          ) : (
            <>
              <Icon name="download" size={16} />
              {updateInfo.is_downgrade ? t("settingsPage.applyDowngrade") : t("settingsPage.applyUpdate")}
            </>
          )}
        </button>
      ) : (
        <a
          href={updateInfo.download_url || updateInfo.html_url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-primary"
          style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px", textDecoration: "none" }}
        >
          <Icon name="download" size={16} />
          {updateInfo.asset_name
            ? `${t("settingsPage.downloadUpdate")} (${updateInfo.asset_name}${updateInfo.asset_size ? ` - ${formatBinarySize(updateInfo.asset_size)}` : ""})`
            : t("settingsPage.downloadUpdate")}
        </a>
      )}
    </div>
  );
}
