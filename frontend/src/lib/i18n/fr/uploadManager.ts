import type { Dict } from "../core.ts";

export const uploadManager: Dict = {
  reencoding: "Réencodage ({{percent}} %)",
  importError: "Erreur lors de l'import",
  uploadError: "Erreur lors de l'upload",
  taskLost: "Tâche perdue (serveur redémarré ou expirée).",
  importFailed: "Échec de l'import",
  kindVideo: "Cours",
  kindBackground: "Fond animé",
  kindAudio: "Cours audio",
  kindRadio: "Musique radio",
  kindAnnouncements: "Rappels radio",
  activeOne: "{{count}} import en cours",
  activeMany: "{{count}} imports en cours",
  doneOne: "{{count}} import terminé",
  doneMany: "{{count}} imports terminés",
  cancelImport: "Annuler l'importation",
  clearDone: "Effacer les terminés",
};
