import type { Dict } from "../../core.ts";

export const cat: Dict = {
  playback: { label: "Lecture et médias", desc: "Compatibilité du navigateur, version vidéo et composant audio natif", keywords: "lecture video media navigateur compatibilite codec h264 hevc version compatible original audio natif web rendition" },
  sound: { label: "Son", desc: "Sortie, volume, rappels et égaliseur de chaque radio ; égaliseur des vidéos", keywords: "son audio radio volume egaliseur basses loudness limiteur rappels sortie mixage video" },
  system: { label: "Système", desc: "Démarrage de Bobine avec l'ordinateur", keywords: "systeme demarrage automatique ordinateur session boot lancement" },
  appearance: { label: "Apparence", desc: "Thème, mode clair ou sombre, langue, logo et qualité du verre", keywords: "theme couleur mode clair sombre automatique langue francais anglais logo verre flou transparence marque" },
  display: { label: "Affichage", desc: "Sortie câblée, écran physique, HDMI et double écran", keywords: "ecran hdmi projecteur television sortie cable double ecran kiosque cinema affichage" },
  inputs: { label: "Entrées", desc: "Touches de la télécommande, de la manette et du clavier", keywords: "entree touche telecommande manette clavier raccourci bouton capture chapitre" },
  updates: { label: "Mises à jour", desc: "Version installée, canal Stable, Bêta ou Canary, mises à jour automatiques", keywords: "version mise a jour canal stable beta canary automatique telechargement" },
  data: { label: "Données et maintenance", desc: "Sauvegarde, restauration, synchronisation et journaux", keywords: "sauvegarde restauration export import synchronisation journaux logs purge nettoyage configuration fichiers" },
  help: { label: "Documentation", desc: "Adresses d'accès, liens des écrans et aide", keywords: "documentation aide adresse lien acces ecran kiosque telecommande bobine.local port reseau" },
  danger: { label: "Zone de danger", desc: "Actions irréversibles : réinitialisation et désinstallation", keywords: "danger reinitialiser reinitialisation desinstaller supprimer effacer redemarrer irreversible" },
};
