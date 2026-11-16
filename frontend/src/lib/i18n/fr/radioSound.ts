import type { Dict } from "../core.ts";

export const radioSound: Dict = {
  title: "Son",
  enabledOn: "Actif",
  enabledOff: "Son neutre",
  enabledHint: "Désactiver l'égaliseur : le son est lu tel quel, sans aucun traitement.",
  presetsLabel: "Préréglages",
  presets: {
    bass: "Bass Boost",
    voice: "Voix Boost",
    soft: "Adoucis",
  },
  bandsLabel: "Égaliseur 5 bandes",
  bass: "Basses",
  loudness: "Loudness",
  loudnessHint: "Relève les graves et les aigus à faible volume.",
  limiter: "Protection saturation",
  limiterHint: "Évite la distorsion quand les réglages relèvent fortement le son.",
  reset: "Réinitialiser",
};
