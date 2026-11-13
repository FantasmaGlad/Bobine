"use client";
import React from "react";
import Link from "next/link";
import Icon from "@/components/Icon";
import { footerNavLinks, navLinks } from "@/lib/navLinks";

export default function CoachNavSheet({ t, onClose }: { t: (key: string, vars?: Record<string, string | number>) => string; onClose: () => void }) {
  return (
    <div className="coach-sheet-overlay" onClick={onClose}>
      <div className="coach-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="coach-sheet-handle" />
        <h3 style={{ margin: "0 0 12px" }}>{t("coach.otherFunctions")}</h3>
        <div className="coach-sheet-list">
          {[...navLinks, ...footerNavLinks].map((link) => (
            <Link key={link.href} href={link.href} className="nav-link" onClick={onClose}>
              <Icon name={link.iconName} size={20} />
              <span>{t(link.labelKey)}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
