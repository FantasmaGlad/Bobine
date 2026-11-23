import type { SignageEntry } from "@/lib/signageLoop";
import { prepareImage } from "./imageSlide";
import type { Slide } from "./slide";
import { prepareVideo } from "./videoSlide";

export function prepareSlide(entry: SignageEntry, src: string, loop: boolean): Promise<Slide | null> {
  return entry.is_image ? prepareImage(src, entry.title) : prepareVideo(src, entry.title, loop);
}
