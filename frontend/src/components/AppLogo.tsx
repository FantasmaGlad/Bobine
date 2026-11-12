"use client";

import React, { useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { channelLogoUrl } from "@/lib/releaseChannel";
import { getApiUrl } from "@/lib/apiUrl";

interface AppLogoProps {
  size?: number;
  className?: string;
}

export default function AppLogo({ size, className }: AppLogoProps) {
  const { hasCustomLogo, activeLogo, logoVersion, updateChannel } = useAppSettings();
  const [customFailed, setCustomFailed] = useState(false);
  useEffect(() => setCustomFailed(false), [logoVersion]);
  const useCustom = activeLogo === "custom" && hasCustomLogo && !customFailed;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={useCustom ? `${getApiUrl("/branding/logo.png")}?v=${logoVersion}` : channelLogoUrl(updateChannel)}
      alt="Bobine"
      className={`app-logo app-logo--custom${className ? ` ${className}` : ""}`}
      style={
        size
          ? { maxHeight: size, maxWidth: "100%", width: "auto", height: "auto", display: "block", objectFit: "contain" }
          : { maxWidth: "100%", maxHeight: "100%", display: "block", objectFit: "contain" }
      }
      onError={() => setCustomFailed(true)}
    />
  );
}
