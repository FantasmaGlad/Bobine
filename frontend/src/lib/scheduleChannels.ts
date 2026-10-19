/**
 * Voies du Planning : quatre voies, chacune pilotant SON moteur de lecture — les canaux de
 * diffusion câblé et réseau (vidéo) et les deux sorties radio (câblée, réseau). Logique PURE,
 * testable (`frontend/tests/`).
 *
 * L'ancienne voie « radio » (voie radio unique d'avant les deux sorties) reste acceptée dans
 * les liens (`/schedule?channel=radio`) et désigne la sortie réseau, comme côté serveur.
 */
export type ScheduleChannel = "cable" | "network" | "radio_cable" | "radio_network";

export const SCHEDULE_CHANNELS: ScheduleChannel[] = ["cable", "network", "radio_cable", "radio_network"];

/** Vrai pour les voies radio : une seule famille de cibles (playlists radio), des fenêtres horaires. */
export function isRadioLane(channel: ScheduleChannel): boolean {
  return channel === "radio_cable" || channel === "radio_network";
}

/** Voie demandée par un lien (`?channel=`) : alias historique `radio` ramené au réseau, valeur
 * absente ou inconnue = câblé (comportement historique). */
export function parseScheduleChannel(requested: string | null | undefined): ScheduleChannel {
  if (requested === "radio") return "radio_network";
  return SCHEDULE_CHANNELS.includes(requested as ScheduleChannel) ? (requested as ScheduleChannel) : "cable";
}
