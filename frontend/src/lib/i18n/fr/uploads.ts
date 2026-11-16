import type { Dict } from "../core.ts";

export const uploads: Dict = {
  phase: { connecting: "Connexion au serveur", sending: "Envoi", processing: "Traitement" },
  retrying: "Le serveur ne répond pas, nouvelle tentative {{attempt}}/{{max}}",
  retryingServerError: "Le serveur a répondu par une erreur ({{status}}), nouvelle tentative {{attempt}}/{{max}}",
  serverUnreachable: "Le serveur ne répond plus : le suivi reprendra dès son retour.",
  reason: {
    network: "erreur réseau",
    timeout: "délai dépassé",
    stalled: "aucune donnée transmise depuis {{seconds}} s",
    server: "erreur serveur {{status}}",
  },
  errors: {
    sessionTimeout: "Le serveur ne répond pas (aucune réponse après {{seconds}} s). Vérifiez que Bobine est démarré, puis réessayez.",
    unreachable: "Impossible de joindre le serveur. Vérifiez que Bobine est démarré et la connexion réseau, puis réessayez.",
    sessionLost: "Session de transfert perdue (le serveur a redémarré ou la session a expiré). Relancez l'import.",
    interrupted: "Transfert interrompu après {{max}} tentatives ({{reason}}).",
    jobLost: "Tâche perdue (serveur redémarré ou expirée). Vérifiez la bibliothèque, puis relancez l'import si le fichier n'y figure pas.",
    mediaToolMissing: "{{tool}} est introuvable : Bobine en a besoin pour analyser et convertir les vidéos. {{hint}}",
    installHint: {
      macos: "Installez-le avec Homebrew (brew install ffmpeg), puis relancez Bobine.",
      windows: "Réinstallez Bobine : ffmpeg est normalement fourni avec l'application.",
      linux: "Installez-le avec votre gestionnaire de paquets (sudo apt install ffmpeg), puis relancez Bobine.",
      android: "Ce composant est fourni avec l'application : réinstallez Bobine.",
    },
  },
};
