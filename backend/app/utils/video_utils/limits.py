"""Délais des appels ffprobe et ffmpeg."""


# Délai maximum accordé à chaque appel ffprobe/ffmpeg :
# ces appels tournent sur l'exécuteur mono-thread PARTAGÉ par tous les imports
# de l'application (app.utils.executors.ffmpeg_executor) — un seul fichier
# problématique (corrompu, flux exotique sur lequel ffmpeg reste bloqué en
# lecture) y bloquerait alors indéfiniment TOUS les imports suivants, upload
# comme dossier surveillé, sans jamais remonter d'erreur ni libérer le
# thread. Un timeout transforme ce blocage silencieux en échec explicite.
FFPROBE_TIMEOUT_SECONDS = 30


FFMPEG_THUMBNAIL_TIMEOUT_SECONDS = 30


# Plus généreux que les deux ci-dessus : laisse la place à un réencodage légitimement
# long tout en bornant le pire cas (fichier corrompu/pathologique).
FFMPEG_NORMALIZE_TIMEOUT_SECONDS = 1800
