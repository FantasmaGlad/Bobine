import { COURSE_AUDIO_EXTENSIONS, hasExtension } from "@/lib/mediaFiles";
import { parseMediaName } from "@/lib/parseMediaName";

export const AUDIO_ACCEPT = `${COURSE_AUDIO_EXTENSIONS.join(",")},audio/*`;

export const isAudioFile = (f: File) => hasExtension(f.name.toLowerCase(), COURSE_AUDIO_EXTENSIONS);

interface FileEntryLike {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file: (cb: (f: File) => void) => void;
  createReader?: () => { readEntries: (cb: (entries: FileEntryLike[]) => void) => void };
}

async function readEntryRecursively(entry: FileEntryLike): Promise<File[]> {
  if (entry.isFile) return new Promise((resolve) => entry.file((f) => resolve(isAudioFile(f) ? [f] : [])));
  if (!entry.isDirectory || !entry.createReader) return [];
  const reader = entry.createReader();
  const all: FileEntryLike[] = [];
  for (;;) {
    const batch: FileEntryLike[] = await new Promise((resolve) => reader.readEntries(resolve));
    if (batch.length === 0) break;
    all.push(...batch);
  }
  return (await Promise.all(all.map(readEntryRecursively))).flat();
}

export async function collectDroppedAudioFiles(dataTransfer: DataTransfer): Promise<{ files: File[]; folderName: string | null }> {
  const items = dataTransfer.items;
  if (!items || items.length === 0 || typeof items[0]?.webkitGetAsEntry !== "function") {
    return { files: Array.from(dataTransfer.files).filter(isAudioFile), folderName: null };
  }
  const entries = Array.from(items)
    .map((item) => item.webkitGetAsEntry() as FileEntryLike | null)
    .filter((e): e is FileEntryLike => e !== null);
  const nested = await Promise.all(entries.map(readEntryRecursively));
  return { files: nested.flat(), folderName: entries.find((e) => e.isDirectory)?.name ?? null };
}

export function folderOf(file: File | undefined): string | null {
  const relPath = (file as (File & { webkitRelativePath?: string }) | undefined)?.webkitRelativePath;
  return relPath ? relPath.split("/")[0] : null;
}

export interface CourseName {
  title: string;
  program?: string;
  release?: string;
}

export function guessCourseName(files: File[], folder: string | null, programs: string[], fallback: string): CourseName {
  if (folder) return parseMediaName(folder, programs);
  const parsed = parseMediaName(files[0].name, programs);
  const known = parsed.program && programs.some((p) => p.toLowerCase() === parsed.program.toLowerCase());
  if (known && parsed.release) return parsed;
  const base = files[0].name.replace(/\.(mp3|m4a|wav|aac|flac|ogg)$/i, "").replace(/^\d+[\s._-]*/, "").split(/[_-]/)[0];
  return { title: base || fallback };
}
