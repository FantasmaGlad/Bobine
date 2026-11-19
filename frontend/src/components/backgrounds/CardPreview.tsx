"use client";

import { useEffect, useRef } from "react";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import { thumbnailUrl } from "@/lib/thumbnail";
import type { BackgroundItem } from "./types";

export default function CardPreview({ bg, hovering }: { bg: BackgroundItem; hovering: boolean }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (hovering && !bg.is_image) {
      video.currentTime = 0;
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  }, [hovering, bg.is_image]);

  const thumbSrc = thumbnailUrl(bg.thumbnail_path);
  if (hovering && !bg.is_image) {
    return (
      <video
        ref={videoRef}
        className="card-thumbnail"
        src={getApiUrl(`/backgrounds/${bg.id}/stream`)}
        muted
        loop
        playsInline
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    );
  }
  if (thumbSrc) {
    return <img src={thumbSrc} alt={bg.title} className="card-thumbnail" style={{ width: "100%", height: "100%", objectFit: "cover" }} />;
  }
  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Icon name={bg.is_image ? "image" : "gradient"} size={32} style={{ opacity: 0.3 }} />
    </div>
  );
}
