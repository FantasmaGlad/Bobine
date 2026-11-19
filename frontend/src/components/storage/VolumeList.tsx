"use client";

import React from "react";
import Icon from "@/components/Icon";
import { type PortableListing, type StorageVolume, type VolumeListing } from "@/lib/storage/types";
import type { ShowToast } from "@/lib/useToast";
import { PortableRow, VolumeRow } from "./VolumeRow";

type Ctx = { t: (key: string, vars?: Record<string, string | number>) => string; lang: "fr" | "en"; notify: ShowToast };

export default function VolumeList({ ctx, listing, portable, opening, onExplore, onMore, onOpenPortable }: {
  ctx: Ctx;
  listing: VolumeListing | null;
  portable: PortableListing | null;
  opening: string | null;
  onExplore: (volume: StorageVolume) => void;
  onMore: (key: string) => void;
  onOpenPortable: (id: string, name: string) => void;
}) {
  const { t } = ctx;
  const volumes = listing?.volumes ?? [];
  const phones = portable?.devices ?? [];
  if (!listing) return <div className="rl-center-note">{t("storage.loading")}</div>;
  if (volumes.length === 0 && phones.length === 0) {
    return (
      <div className="rl-empty-state">
        <Icon name="usb" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
        <p style={{ margin: 0, fontWeight: 600 }}>{t("storage.empty")}</p>
      </div>
    );
  }
  return (
    <div className="dv-list">
      {volumes.map((volume) => (
        <VolumeRow key={volume.key} {...ctx} volume={volume} busy={opening === volume.key} onExplore={() => onExplore(volume)} onMore={() => onMore(volume.key)} />
      ))}
      {phones.map((device) => (
        <PortableRow key={device.id} {...ctx} device={device} busy={opening === device.id} onOpen={() => onOpenPortable(device.id, device.name)} />
      ))}
    </div>
  );
}
