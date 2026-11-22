import type { Dict } from "../../core.ts";

export const cat: Dict = {
  playback: { label: "Playback and media", desc: "Browser compatibility, video version and native audio component", keywords: "playback video media browser compatibility codec h264 hevc compatible original native audio web rendition" },
  system: { label: "System", desc: "Start Bobine with the computer", keywords: "system startup automatic computer session boot launch" },
  appearance: { label: "Appearance", desc: "Theme, light or dark mode, language, logo and glass quality", keywords: "theme color mode light dark automatic language french english logo glass blur transparency brand" },
  display: { label: "Display", desc: "Wired output, physical screen, HDMI and dual screen", keywords: "screen hdmi projector television wired output dual screen kiosk cinema display" },
  inputs: { label: "Inputs", desc: "Remote, gamepad and keyboard keys", keywords: "input key remote gamepad keyboard shortcut button capture chapter" },
  updates: { label: "Updates", desc: "Installed version, Stable, Beta or Canary channel, automatic updates", keywords: "version update channel stable beta canary automatic download" },
  data: { label: "Data and maintenance", desc: "Backup, restore, synchronization and logs", keywords: "backup restore export import synchronization logs purge cleanup configuration files" },
  help: { label: "Documentation", desc: "Access addresses, screen links and help", keywords: "documentation help address link access screen kiosk remote bobine.local port network" },
  danger: { label: "Danger zone", desc: "Irreversible actions: reset and uninstall", keywords: "danger reset uninstall delete erase restart irreversible" },
};
