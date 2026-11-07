/**
 * Reconnaissance des fichiers vidéo à l'import, indépendante du navigateur.
 *
 * Pourquoi pas `File.type.startsWith("video/")` seul (ancien comportement du
 * glisser-déposer de la bibliothèque) : le type MIME d'un `File` est déduit
 * par le NAVIGATEUR depuis la base de types du système d'exploitation. Selon
 * Firefox/OS, il est vide pour des extensions pourtant courantes (`.mkv`,
 * `.ts`, `.mov`, `.m4v`…) — le fichier était alors ignoré SANS aucun message
 * (constaté sous Firefox).
 * L'extension fait donc foi en second recours ; la validation réelle du
 * contenu reste faite côté serveur par ffprobe.
 */

export const VIDEO_EXTENSIONS = [
  "mp4", "m4v", "mov", "mkv", "webm", "avi", "wmv", "flv", "mpg", "mpeg", "ts", "m2ts", "mts", "3gp", "ogv",
] as const;

/** Valeur de l'attribut `accept` des champs fichier vidéo : MIME + extensions
 * (le sélecteur de Firefox s'appuie sur la même base de types que `File.type`). */
export const VIDEO_ACCEPT = ["video/*", ...VIDEO_EXTENSIONS.map((ext) => `.${ext}`)].join(",");

const VIDEO_EXTENSION_SET: ReadonlySet<string> = new Set(VIDEO_EXTENSIONS);

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

export function isVideoFile(file: File): boolean {
  return file.type.startsWith("video/") || VIDEO_EXTENSION_SET.has(fileExtension(file.name));
}

/** Radio : tous les formats audio (miroir de `RADIO_AUDIO` dans `backend/app/utils/media_formats.py`, vérifié par un test). */
export const RADIO_AUDIO_EXTENSIONS = [
  ".mp3", ".m4a", ".aac", ".mp4", ".ogg", ".oga", ".opus", ".webm", ".flac", ".wav",
  ".wma", ".aiff", ".aif", ".aifc", ".ape", ".alac", ".wv", ".mka", ".m4b", ".ac3",
] as const;
/** Cours audio : formats lus tels quels (miroir de `COURSE_AUDIO`). */
export const COURSE_AUDIO_EXTENSIONS = [".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".oga", ".opus"] as const;

export function hasExtension(name: string, extensions: readonly string[]): boolean {
  const lower = name.toLowerCase();
  return extensions.some((ext) => lower.endsWith(ext));
}

export const SUBTITLE_EXTENSIONS = ["srt", "vtt"] as const;
const SUBTITLE_EXTENSION_SET: ReadonlySet<string> = new Set(SUBTITLE_EXTENSIONS);

export function isSubtitleFile(file: File): boolean {
  return SUBTITLE_EXTENSION_SET.has(fileExtension(file.name));
}

export interface PartitionedFiles {
  accepted: File[];
  subtitles: File[];
  rejected: File[];
}

export function partitionVideoFiles(files: File[]): PartitionedFiles {
  const accepted: File[] = [];
  const subtitles: File[] = [];
  const rejected: File[] = [];
  for (const file of files) {
    if (isVideoFile(file)) {
      accepted.push(file);
    } else if (isSubtitleFile(file)) {
      subtitles.push(file);
    } else {
      rejected.push(file);
    }
  }
  return { accepted, subtitles, rejected };
}

/** Archives d'import acceptées (mêmes extensions que `ARCHIVE_EXTENSIONS` côté serveur, qui reconnaît le format au contenu). */
export const ARCHIVE_EXTENSIONS = [".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2"] as const;
export const ARCHIVE_ACCEPT = ARCHIVE_EXTENSIONS.join(",");

export function isArchiveName(name: string): boolean {
  const lower = name.toLowerCase();
  return ARCHIVE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}
