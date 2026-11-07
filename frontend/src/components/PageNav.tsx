"use client";

import React from "react";
import SegmentedTabs, { type SegmentedTab } from "@/components/SegmentedTabs";

interface PageNavProps {
  tabs: SegmentedTab[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  /** Actions propres à la page (import, filtres) : à droite des onglets, qui passent au-dessus sur téléphone. */
  actions?: React.ReactNode;
  className?: string;
}

/**
 * Barre de navigation de page, la même partout : sections en onglets segmentés (indicateur glissant, défilement
 * horizontal sur petit écran) dans la carte commune des pages, avec les actions de la page à droite. Toute page à
 * plusieurs sections ou vues l'utilise : pas de balisage ni de classes propres à une page.
 */
export default function PageNav({ tabs, value, onChange, ariaLabel, actions, className = "" }: PageNavProps) {
  return (
    <div className={`live-block channel-card rl-nav-card page-nav ${className}`.trim()}>
      <div className="channel-card-right page-nav-tabs">
        <SegmentedTabs tabs={tabs} value={value} onChange={onChange} ariaLabel={ariaLabel} />
      </div>
      {actions ? <div className="page-nav-actions">{actions}</div> : null}
    </div>
  );
}
