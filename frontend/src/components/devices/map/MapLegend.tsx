"use client";

import { linkStyle, type Topology } from "@/lib/deviceMap";
import { type SectionProps } from "../common";
import MediumLine from "./MediumLine";

const MEDIA = ["wifi", "bluetooth", "wired"] as const;

export default function MapLegend({ counts, t }: { counts: Topology["counts"]; t: SectionProps["t"] }) {
  return (
    <div className="dv-map-legend" aria-label={t("devices.map.legend")}>
      {MEDIA.map((medium) => (
        <span key={medium} className="dv-legend-item">
          <MediumLine medium={medium} style={linkStyle(medium)} />
          {t(`devices.map.medium.${medium}`)}
        </span>
      ))}
      <span className="dv-legend-item dv-legend-count">{t("devices.map.counts", { audio: counts.audio, bluetooth: counts.bluetooth, screens: counts.screens })}</span>
    </div>
  );
}
