import type { UpdateChannel } from "@/lib/releaseChannel";

export type DeploymentProfile = "linux-headless" | "linux-desktop" | "windows" | "macos" | "android";

export interface SettingsData {
  restart_guaranteed?: boolean;
  wait_time_between_courses: number;
  volume_default: number;
  audio_chain_timer_seconds: number;
  radio_announcement_fade_ms: number;
  logs_retention_days?: number;
  deployment_profile: DeploymentProfile;
  paths: Record<string, string>;
  network: {
    local_ip: string | null;
    port: number;
    mdns_url: string;
    mdns_status: string | null;
    port80_redirect?: boolean;
    access?: { kind: "loopback" | "lan" | "vpn" | "mdns"; interface: string; url: string }[];
  };
  update_channel: UpdateChannel;
  wired_display_mode: "dual_screen" | "headless";
  auto_update_enabled: "true" | "false";
  auto_update_time: string;
  auto_update_supported?: boolean;
  update_tor_supported?: boolean;
  update_tor?: "true" | "false";
  update_tor_proxy?: string;
  store_managed?: boolean;
}

export interface StoreInfo {
  provider: "google_play";
  state: "none" | "available" | "downloading" | "downloaded" | "installing" | "failed" | "unavailable";
  version_code?: number | null;
  message?: string;
}

export interface UpdateInfo {
  online: boolean;
  channel?: UpdateChannel;
  current_version: string;
  current_tag: string;
  current_commit: string;
  latest_version: string | null;
  has_update: boolean;
  is_downgrade?: boolean;
  error_code?: "offline" | "rate_limited" | `not_found_${UpdateChannel}` | null;
  local_build?: UpdateChannel;
  release_title: string | null;
  release_notes: string | null;
  published_at: string | null;
  html_url: string | null;
  can_auto_apply?: boolean;
  store_managed?: boolean;
  store?: StoreInfo;
  download_url?: string | null;
  asset_name?: string | null;
  asset_size?: number | null;
  deployment_profile?: DeploymentProfile;
  message?: string;
  checked_at: string;
}
