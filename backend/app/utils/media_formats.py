"""Extensions de fichiers acceptées à l'import : la liste unique du serveur.

Le frontend en garde le miroir dans `frontend/src/lib/mediaFiles.ts` (filtrage des dossiers déposés) ;
`backend/tests/test_media_formats.py` vérifie que les deux listes sont identiques.
"""
from __future__ import annotations

# Lus tels quels par Chromium : servis sans transcodage.
WEB_PLAYABLE_AUDIO = frozenset({".mp3", ".m4a", ".aac", ".mp4", ".ogg", ".oga", ".opus", ".webm", ".flac", ".wav"})
# Radio : tous les formats audio ; ceux qui ne sont pas lisibles par le navigateur sont transcodés en AAC à l'import.
RADIO_AUDIO = WEB_PLAYABLE_AUDIO | {".wma", ".aiff", ".aif", ".aifc", ".ape", ".alac", ".wv", ".mka", ".m4b", ".ac3"}
# Cours audio : jamais transcodés, donc seulement les formats audio lisibles tels quels (ni .mp4 ni .webm, conteneurs vidéo).
COURSE_AUDIO = frozenset({".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".oga", ".opus"})
# Exploration d'un support : tous les formats audio, hors conteneurs vidéo.
SUPPORT_AUDIO = RADIO_AUDIO - {".mp4", ".webm"}
VIDEO = frozenset({".mp4", ".m4v", ".mkv", ".avi", ".mov"})
IMAGE = frozenset({".png", ".jpg", ".jpeg", ".webp"})
SUBTITLE = frozenset({".srt", ".vtt"})
ARCHIVE = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")
