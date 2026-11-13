import { getApiUrl } from "@/lib/apiUrl";

interface PlaylistItemRef {
  video: { id: number };
}

export async function deleteVideos(ids: number[]): Promise<number> {
  const results = await Promise.allSettled(ids.map((id) => fetch(getApiUrl(`/videos/${id}`), { method: "DELETE" })));
  return results.filter((r) => r.status === "rejected" || !r.value.ok).length;
}

export async function appendToPlaylist(playlistId: string, videoIds: number[]): Promise<string> {
  const res = await fetch(getApiUrl(`/playlists/${playlistId}`), { cache: "no-store" });
  if (!res.ok) throw new Error();
  const playlist = await res.json();
  const items: PlaylistItemRef[] = playlist.items;
  const existing = items.map((i) => i.video.id);
  const additions = videoIds.filter((id) => !existing.includes(id));
  const body = {
    name: playlist.name,
    items: [
      ...items.map((i, idx) => ({ video_id: i.video.id, position: idx })),
      ...additions.map((id, idx) => ({ video_id: id, position: items.length + idx })),
    ],
  };
  const put = await fetch(getApiUrl(`/playlists/${playlistId}`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!put.ok) throw new Error();
  return playlist.name;
}
