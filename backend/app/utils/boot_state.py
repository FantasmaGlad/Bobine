import uuid

# Identifiant stable pour toute la durée de vie de CE process, généré une
# seule fois à l'import du module. Change à chaque lancement du service
# (redémarrage, mise à jour, coupure) — c'est tout ce qu'exige son seul
# usage restant : signaler aux clients déjà connectés qu'un redémarrage a eu
# lieu depuis leur connexion initiale, pour qu'ils se rechargent entièrement
# au lieu de rester sur leur ancien bundle JS/HTML (cf. routers/playback.py).
#
# Avant PortabiliteCrossPlatformX Lot 0, cette valeur était calculée à partir
# du PID du processus parent + son instant de démarrage (lu dans
# /proc/<pid>/stat) pour rester identique entre les 4 workers uvicorn d'un
# même lancement, et partagée via Redis pour piloter la purge de l'état de
# lecture au démarrage. Process unique depuis ce lot : un simple identifiant
# aléatoire généré une fois par process suffit, sans dépendance à /proc
# (Linux uniquement) ni à un état partagé externe.
_BOOT_ID = uuid.uuid4().hex


def current_boot_id() -> str:
    return _BOOT_ID
