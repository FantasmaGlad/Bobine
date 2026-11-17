import React from "react";
import Icon from "@/components/Icon";
import { fsLabel } from "@/lib/storage/advice";
import { formatBytes } from "@/lib/storage/display";
import type { FormatPlan } from "@/lib/storage/format";
import type { Lang, T } from "../common";

function contentLine(plan: FormatPlan, t: T): string {
  const media = plan.content.volumes.reduce((acc, v) => ({ video: acc.video + (v.media?.video ?? 0), audio: acc.audio + (v.media?.audio ?? 0) }), { video: 0, audio: 0 });
  const files = plan.erases.truncated
    ? t("storage.format.filesMore", { files: plan.erases.files })
    : t("storage.format.filesLine", { files: plan.erases.files, dirs: plan.content.volumes.reduce((n, v) => n + (v.dirs ?? 0), 0) });
  return files + ((media.video || media.audio) ? ` · ${t("storage.format.mediaLine", { videos: media.video, tracks: media.audio })}` : "");
}

export default function EraseSummary({ plan, t, lang }: { plan: FormatPlan; t: T; lang: Lang }) {
  const volume = plan.content.volumes[0];
  const roots = plan.content.volumes.flatMap((v) => v.root ?? []).slice(0, 8).map((e) => e.name).join(", ");
  return (
    <>
      <div className="fmt-erase" role="note">
        <strong>{t("storage.format.warning")}</strong>
        <span className="dv-sub">{t("storage.format.erasesLine", { partitions: plan.erases.partitions, files: plan.erases.files })}</span>
        {volume?.readable !== false && plan.erases.files > 0 && <span className="dv-sub">{contentLine(plan, t)}</span>}
        {roots && <span className="dv-sub">{t("storage.format.rootLine", { names: roots })}</span>}
        {plan.erases.unreadable && <span className="dv-sub">{t("storage.format.unreadable")}</span>}
      </div>
      <div className="dv-detail-block">
        <div className="dv-row">
          <span className="dv-icon"><Icon name="usb" size={22} /></span>
          <span className="dv-text">
            <span className="dv-title">{plan.target.name}</span>
            <span className="dv-sub">
              {t("storage.format.currentLine", {
                fs: plan.target.partitions.map((p) => fsLabel(p.fstype)).join(" + ") || "—",
                used: formatBytes(plan.content.bytes_used, lang),
                size: formatBytes(plan.target.size_bytes, lang),
              })}
            </span>
          </span>
        </div>
      </div>
    </>
  );
}
