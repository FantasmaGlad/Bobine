import type { Dict } from "../core.ts";

export const webRendition: Dict = {
  title: "Lisible sur tous les navigateurs",
  notSafe: "Ce fichier utilise un format que certains navigateurs ne savent pas lire ({{issues}}). L'original est conservé pour la sortie HDMI.",
  create: "Créer la version compatible",
  creating: "Production en cours…",
  ready: "Version compatible prête : servie automatiquement aux navigateurs qui en ont besoin.",
  remove: "Supprimer la version compatible",
  failed: "La production a échoué — réessayez.",
  queued: "Production lancée : suivi dans la liste des imports.",
  issueCodec: "codec {{codec}}",
  issuePixel: "format de pixels 10 bits / 4:2:2",
};
