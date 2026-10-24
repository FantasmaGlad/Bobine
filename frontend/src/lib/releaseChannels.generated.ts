// Généré par scripts/sync_release_channels.py depuis backend/app/release_channel.py.
// Ne pas modifier à la main : ajouter un canal commence dans le registre du backend.
export const RELEASE_CHANNELS = ["stable", "beta", "canary"] as const;
export const DEFAULT_RELEASE_CHANNEL = "stable" as const;
export const ROLLING_RELEASE_CHANNELS = ["beta", "canary"] as const;
