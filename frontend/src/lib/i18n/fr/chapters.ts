import type { Dict } from "../core.ts";

export const chapters: Dict = {
  title: "Chapitres",
  toastLabel: "Chapitre",
  import: "Importer (.json, .vtt, .txt)",
  fromFile: "Lire dans la vidéo",
  export: "Exporter",
  addHere: "Ajouter ici",
  save: "Enregistrer les chapitres",
  saved: "Chapitres enregistrés",
  empty: "Aucun chapitre. Importez un fichier ou ajoutez-en depuis le lecteur.",
  titlePlaceholder: "Titre du chapitre",
  remove: "Supprimer ce chapitre",
  importHint: "Format JSON : { \"chapters\": [ { \"start\": \"05:00\", \"title\": \"Cardio\" } ] } — ou une liste « 05:00 Titre », ou un fichier WebVTT.",
  error: "Chapitres non enregistrés",
};
