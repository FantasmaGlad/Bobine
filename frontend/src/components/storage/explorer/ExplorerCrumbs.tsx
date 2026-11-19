"use client";

import Icon from "@/components/Icon";
import type { breadcrumbs } from "@/lib/storage/browse";
import { type StorageCtx } from "../common";

export default function ExplorerCrumbs({ t, crumbs, rootName, goTo }: {
  t: StorageCtx["t"]; crumbs: ReturnType<typeof breadcrumbs>; rootName: string; goTo: (target: string) => void;
}) {
  return (
    <nav className="st-crumbs" aria-label={t("storage.explorer.root")}>
      {crumbs.map((crumb, index) => (
        <span key={crumb.path} className="st-crumb">
          {index > 0 && <Icon name="chevron_right" size={16} />}
          <button type="button" className="dv-link-btn" aria-current={index === crumbs.length - 1 ? "page" : undefined} onClick={() => goTo(crumb.path)}>
            {crumb.label ?? rootName}
          </button>
        </span>
      ))}
    </nav>
  );
}
