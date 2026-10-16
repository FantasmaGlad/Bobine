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

export const SUBTITLE_EXTENSIONS = ["srt", "vtt"] as const;
export const SUBTITLE_ACCEPT = [".srt", ".vtt", "text/vtt", "application/x-subrip"].join(",");
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

