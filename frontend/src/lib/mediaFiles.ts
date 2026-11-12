export const VIDEO_EXTENSIONS = [
  "mp4", "m4v", "mov", "mkv", "webm", "avi", "wmv", "flv", "mpg", "mpeg", "ts", "m2ts", "mts", "3gp", "ogv",
] as const;

export const VIDEO_ACCEPT = ["video/*", ...VIDEO_EXTENSIONS.map((ext) => `.${ext}`)].join(",");

const VIDEO_EXTENSION_SET: ReadonlySet<string> = new Set(VIDEO_EXTENSIONS);

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

export function isVideoFile(file: File): boolean {
  return file.type.startsWith("video/") || VIDEO_EXTENSION_SET.has(fileExtension(file.name));
}

export const RADIO_AUDIO_EXTENSIONS = [
  ".mp3", ".m4a", ".aac", ".mp4", ".ogg", ".oga", ".opus", ".webm", ".flac", ".wav",
  ".wma", ".aiff", ".aif", ".aifc", ".ape", ".alac", ".wv", ".mka", ".m4b", ".ac3",
] as const;
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

export const ARCHIVE_EXTENSIONS = [".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2"] as const;
export const ARCHIVE_ACCEPT = ARCHIVE_EXTENSIONS.join(",");

export function isArchiveName(name: string): boolean {
  const lower = name.toLowerCase();
  return ARCHIVE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}
