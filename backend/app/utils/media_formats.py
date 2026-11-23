"""Extensions de fichiers acceptées à l'import : la liste unique du serveur."""
from __future__ import annotations

WEB_PLAYABLE_AUDIO = frozenset({".mp3", ".m4a", ".aac", ".mp4", ".ogg", ".oga", ".opus", ".webm", ".flac", ".wav"})
RADIO_AUDIO = WEB_PLAYABLE_AUDIO | {".wma", ".aiff", ".aif", ".aifc", ".ape", ".alac", ".wv", ".mka", ".m4b", ".ac3"}
COURSE_AUDIO = frozenset({".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".oga", ".opus"})
SUPPORT_AUDIO = RADIO_AUDIO - {".mp4", ".webm"}
VIDEO = frozenset({".mp4", ".m4v", ".mkv", ".avi", ".mov"})
IMAGE = frozenset({".png", ".jpg", ".jpeg", ".webp"})
BACKGROUND_IMAGE = IMAGE | {".gif"}
CONVERTED_IMAGE = frozenset({".avif", ".apng", ".bmp", ".dib", ".tif", ".tiff", ".tga", ".ico", ".cur", ".icns", ".pcx",
                             ".ppm", ".pgm", ".pbm", ".pnm", ".qoi", ".sgi", ".dds", ".jfif", ".jpe", ".jp2", ".j2k"})
BACKGROUND_IMAGE_SOURCES = BACKGROUND_IMAGE | CONVERTED_IMAGE
BACKGROUND_VIDEO = VIDEO | {".webm", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".m2ts", ".mts", ".3gp", ".ogv"}
SUBTITLE = frozenset({".srt", ".vtt"})
ARCHIVE = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")
