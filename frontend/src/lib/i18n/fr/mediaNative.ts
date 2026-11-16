import type { Dict } from "../core.ts";

export const mediaNative: Dict = {
  section: "Composant audio natif (expérimental)",
  hint: "Lit les tags, la durée et la pochette des nouveaux morceaux avec un petit programme intégré, sans lancer ffmpeg pour chaque fichier : les imports de bibliothèques audio sont plus rapides et moins gourmands. Désactivé par défaut. Les morceaux déjà importés ne changent pas, et si le composant est absent, échoue ou ne reconnaît pas un fichier, Bobine utilise la méthode habituelle : aucun morceau n'est perdu.",
  label: "Activer le composant audio natif (expérimental)",
  state_disabled: "État : désactivé. Bobine utilise la méthode habituelle.",
  state_active: "État : actif, les formats pris en charge sont lus nativement.",
  state_fallback: "État : repli. Le composant est présent mais ne répond pas ; la méthode habituelle est utilisée.",
  state_absent: "État : absent. Ce paquet ne contient pas le composant ; la méthode habituelle est utilisée.",
  stateUnknown: "État : indisponible (le serveur n'a pas répondu).",
  forcedOn: "Activé par la variable d'environnement BOBINE_MEDIA_NATIVE : elle l'emporte sur ce réglage.",
  forcedOff: "Désactivé par la variable d'environnement BOBINE_MEDIA_NATIVE : elle l'emporte sur ce réglage.",
  saveError: "Le réglage n'a pas pu être enregistré.",
};
