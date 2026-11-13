import { getApiUrl } from "@/lib/apiUrl";

export function thumbnailUrl(path: string | null | undefined): string | null {
  const filename = path?.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}
