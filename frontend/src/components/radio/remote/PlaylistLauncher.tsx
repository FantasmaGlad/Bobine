"use client";

import React, { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMinutes } from "@/lib/format";
import type { RadioPlaylistSummary, SendRadioCommand } from "./types";

export default function PlaylistLauncher({ sendCommand }: { sendCommand: SendRadioCommand }) {
  const { t } = useAppSettings();
  const [playlists, setPlaylists] = useState<RadioPlaylistSummary[]>([]);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string>("");
  const [shuffleOnLoad, setShuffleOnLoad] = useState(false);

  useEffect(() => {
    fetch(getApiUrl("/radio/playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setPlaylists)
      .catch(() => setPlaylists([]));
  }, []);

  const launch = () => {
    if (!selectedPlaylistId) return;
    sendCommand("load_radio_playlist", { playlist_id: Number(selectedPlaylistId), shuffle: shuffleOnLoad });
  };

  return (
    <div className="launch-block">
      <h3>{t("radioRemote.loadPlaylistTitle")}</h3>
      <div className="launch-row launch-row--stacked">
        <ResponsiveSelect
          style={{ flex: 1, minWidth: 0 }}
          value={selectedPlaylistId}
          onChange={setSelectedPlaylistId}
          placeholder={t("radioRemote.choosePlaylist")}
          title={t("radioRemote.loadPlaylistTitle")}
          options={playlists.map((p) => ({
            value: String(p.id),
            label: p.name,
            sublabel: t("radioRemote.playlistTracksCount", { count: p.item_count }),
            thumbnail: p.cover_track_id != null ? getApiUrl(`/radio/tracks/${p.cover_track_id}/cover`) : null,
            square: true,
            meta: formatMinutes(p.total_duration_seconds, "0 min"),
          }))}
        />
        <button className="btn btn-primary" onClick={launch} disabled={!selectedPlaylistId}>
          <Icon name="play_arrow" size={16} filled />
          {t("radioRemote.launch")}
        </button>
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "10px", fontSize: "0.85rem", color: "var(--text-muted)" }}>
        <input type="checkbox" checked={shuffleOnLoad} onChange={(e) => setShuffleOnLoad(e.target.checked)} />
        {t("radioRemote.shuffleOnLoad")}
      </label>
      <button className="btn btn-secondary" style={{ width: "100%", marginTop: "12px" }} onClick={() => sendCommand("radio_shuffle_all")}>
        <Icon name="shuffle" size={16} />
        {t("radioRemote.shuffleAll")}
      </button>
      {playlists.length === 0 && <p className="live-empty" style={{ marginTop: "12px" }}>{t("radioRemote.noPlaylists")}</p>}
    </div>
  );
}
