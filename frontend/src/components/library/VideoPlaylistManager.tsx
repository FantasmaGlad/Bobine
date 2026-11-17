"use client";

import React, { useCallback, useEffect, useState } from "react";
import PlaylistEditorLayout from "@/components/playlist-editor/PlaylistEditorLayout";
import { usePlaylistEditor } from "@/components/playlist-editor/usePlaylistEditor";
import { usePlaylistLaunch } from "@/components/playlist-editor/usePlaylistLaunch";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { useIsMobile } from "@/lib/useIsMobile";
import { usePlaylistSequencer } from "@/lib/usePlaylistSequencer";
import { useToast } from "@/lib/useToast";
import VideoPicker from "./playlist/VideoPicker";
import VideoSequencer from "./playlist/VideoSequencer";
import type { PlaylistDetail, PlaylistItemInput, Video } from "./playlist/types";

const itemsFrom = (detail: PlaylistDetail) => detail.items.map((item) => item.video);
const payload = (items: Video[]): PlaylistItemInput[] => items.map((video, index) => ({ video_id: video.id, position: index }));

export default function VideoPlaylistManager() {
  const { t } = useAppSettings();
  const isMobile = useIsMobile();
  const { toast, showToast } = useToast();
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const editor = usePlaylistEditor<Video, PlaylistDetail>({ endpoint: "/playlists", prefix: "playlists", itemsFrom, payload, t, showToast });
  const { draft, fetchPlaylists } = editor;
  const sequencer = usePlaylistSequencer(draft.setPlaylistItems, (id) => videos.find((v) => v.id === id));
  const launch = usePlaylistLaunch("playlists", t, showToast, "load_playlist", "playlist_id");

  const fetchVideos = useCallback(() => fetch(getApiUrl("/videos?sort_by=imported_at&order=desc"), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setVideos(await res.json());
    })
    .catch(() => showToast(t("playlists.videosNetworkError"), "error")), [showToast, t]);

  useEffect(() => {
    Promise.all([fetchPlaylists(), fetchVideos()]).finally(() => setLoading(false));
  }, [fetchPlaylists, fetchVideos]);

  const handleAddVideo = (video: Video) => {
    draft.setPlaylistItems((prev) => [...prev, video]);
    showToast(t("playlists.addedToast", { title: video.title }));
  };

  return (
    <PlaylistEditorLayout
      editor={editor} prefix="playlists" placeholderIcon="edit_note" t={t} isMobile={isMobile} loading={loading} toast={toast}
      totalDurationSeconds={draft.playlistItems.reduce((acc, item) => acc + (item.duration_seconds ?? 0), 0)}
      statusOnMobile onLaunch={launch}
      sequencer={<VideoSequencer t={t} isMobile={isMobile} playlistItems={draft.playlistItems} sequencer={sequencer} />}
      picker={<VideoPicker key={draft.selectedPlaylistId ?? "new"} t={t} isMobile={isMobile} videos={videos} sequencer={sequencer} handleAddVideo={handleAddVideo} />}
    />
  );
}
