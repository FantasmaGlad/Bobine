"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useInterpolatedPosition } from "@/lib/useInterpolatedPosition";
import { RadioEvent, RadioRepeatMode, useRadioSocket } from "@/lib/useRadioSocket";
import type { RadioChannelId } from "@/lib/displayChannel";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import Icon from "@/components/Icon";
import RadioSoundPanel from "@/components/RadioSoundPanel";
import RadioQueueList from "@/components/RadioQueueList";
import SearchBox from "@/components/SearchBox";
import Highlight from "@/components/Highlight";
import { rankByQuery } from "@/lib/searchText";

// Télécommande d'UNE sortie radio (câblée ou réseau) : pilote le RadioPlaybackManager de la
// sortie à distance (mobile + PC). Le lecteur réel est l'écran /radio?channel=… ; ce composant
// pilote le moteur (playlist, file d'attente, shuffle, repeat).
//
// SEULE implémentation de l'interface de pilotage radio : montée par la page /radio-remote
// (onglets Câblée / Réseau) ET par la page « Sortie Câblé » quand l'écran câblé est en mode
// Radio — jamais recopiée. À monter avec `key={channel}` : changer de sortie repart d'un
// état et d'une connexion neufs plutôt que d'afficher un instant l'état de l'autre sortie.

interface RadioPlaylistSummary {
  id: number;
  name: string;
  is_default: boolean;
  item_count: number;
  total_duration_seconds: number;
  /** Morceau dont la pochette illustre la playlist (1er morceau ayant une pochette). */
  cover_track_id?: number | null;
}

interface RadioTrackSearchResult {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
  genre?: string | null;
  duration_seconds: number | null;
  has_cover?: boolean;
}

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

function formatTime(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDuration(seconds: number) {
  if (!seconds) return "0 min";
  const mins = Math.round(seconds / 60);
  return `${mins} min`;
}

const REPEAT_CYCLE: RadioRepeatMode[] = ["off", "playlist", "track"];

interface RadioRemotePanelProps {
  /** Sortie radio pilotée : un moteur indépendant par sortie côté serveur. */
  channel: RadioChannelId;
  /** "compact" : transport, volume et chargement de playlist seulement (écrans étroits ou
   * tactiles, p. ex. /grid) — sans file d'attente ni recherche. */
  variant?: "full" | "compact";
}

export default function RadioRemotePanel({ channel, variant = "full" }: RadioRemotePanelProps) {
  const { t } = useAppSettings();
  const [lastCause, setLastCause] = useState("sync");
  const handleRadioEvent = (evt: RadioEvent) => setLastCause(evt.cause);
  const { state, connected, sendCommand } = useRadioSocket(handleRadioEvent, undefined, channel);
  const livePosition = useInterpolatedPosition(state.position_seconds, state.playing, lastCause);

  const [playlists, setPlaylists] = useState<RadioPlaylistSummary[]>([]);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string>("");
  const [shuffleOnLoad, setShuffleOnLoad] = useState(false);
  const [seekDragValue, setSeekDragValue] = useState<number | null>(null);
  const [volumeDragValue, setVolumeDragValue] = useState<number | null>(null);
  const [queueSearch, setQueueSearch] = useState("");

  useEffect(() => {
    fetch(getApiUrl("/radio/playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setPlaylists)
      .catch(() => setPlaylists([]));
  }, []);

  // Bibliothèque chargée UNE fois et filtrée ici : la recherche du serveur compare les accents tels
  // quels (« ete » ne trouvait pas « Été indien ») ; le filtre local (lib/searchText.ts) les ignore et
  // fournit aussi l'autocomplétion sur toute la bibliothèque, pas seulement sur les derniers résultats.
  const [allTracks, setAllTracks] = useState<RadioTrackSearchResult[]>([]);
  useEffect(() => {
    if (variant !== "full") return;
    fetch(getApiUrl("/radio/tracks"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setAllTracks)
      .catch(() => setAllTracks([]));
  }, [variant]);
  const queueResults = useMemo(
    () =>
      queueSearch.trim()
        ? rankByQuery(allTracks, queueSearch, (track) => `${track.title} ${track.artist ?? ""} ${track.album ?? ""} ${track.genre ?? ""}`).slice(0, 8)
        : [],
    [allTracks, queueSearch],
  );

  const currentTrack = state.current_track;
  const coverSrc = currentTrack?.cover_url ? getApiUrl(currentTrack.cover_url) : null;
  const duration = state.duration_seconds ?? currentTrack?.duration_seconds ?? 0;
  const displayPosition = seekDragValue ?? livePosition;
  const displayVolume = volumeDragValue ?? state.volume;
  const queue = state.index !== null ? state.order.slice(state.index + 1) : [];
  const queueSeconds = queue.reduce((total, track) => total + (track.duration_seconds ?? 0), 0);
  // Textes proposés par l'autocomplétion : titres, artistes, albums et styles de toute la bibliothèque.
  const queueSuggestions = useMemo(
    () => allTracks.flatMap((track) => [track.title, track.artist, track.album, track.genre].filter((x): x is string => !!x)),
    [allTracks],
  );


  const handleLaunch = () => {
    if (!selectedPlaylistId) return;
    sendCommand("load_radio_playlist", { playlist_id: Number(selectedPlaylistId), shuffle: shuffleOnLoad });
  };

  const handlePlayPause = () => sendCommand(state.playing ? "pause" : "play");

  const handleRepeatCycle = () => {
    const next = REPEAT_CYCLE[(REPEAT_CYCLE.indexOf(state.repeat) + 1) % REPEAT_CYCLE.length];
    sendCommand("radio_set_repeat", { mode: next });
  };

  const repeatLabel =
    state.repeat === "track" ? t("radioRemote.repeatTrack") : state.repeat === "playlist" ? t("radioRemote.repeatPlaylist") : t("radioRemote.repeatOff");

  return (
    <>
      <div className="live-block bento-hero-live" style={{ position: "relative", overflow: "hidden" }}>
        {coverSrc && (
          <div
            className="bento-hero-backdrop"
            style={{ backgroundImage: `url(${coverSrc})`, opacity: 0.25 }}
          />
        )}

        <div className="bento-hero-content">
          <div className="live-header">
            <h3>
              <Icon name="graphic_eq" size={18} />
              {t("radioRemote.title")}
            </h3>
            <span className={`status-pill ${connected ? "ok" : "down"}`}>
              {!connected ? t("radioRemote.disconnected") : t(`radioRemote.stateLabels.${state.state}`)}
            </span>
          </div>

          {state.playlist_name && (
            <div
              style={{
                fontSize: "0.85rem",
                color: "var(--accent-primary)",
                fontWeight: 700,
                background: "color-mix(in srgb, var(--accent-primary) 6%, transparent)",
                padding: "8px 14px",
                borderRadius: "var(--radius-md)",
                border: "1px solid color-mix(in srgb, var(--accent-primary) 20%, transparent)",
                width: "fit-content",
              }}
            >
              {t("radioRemote.playlistLabel", {
                name: state.playlist_name,
                index: (state.index ?? 0) + 1,
                total: state.order.length,
              })}
            </div>
          )}

          {currentTrack ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: "18px", flexWrap: "wrap" }}>
                {coverSrc ? (
                  <img
                    src={coverSrc}
                    alt=""
                    style={{
                      width: "104px",
                      height: "104px",
                      objectFit: "cover",
                      borderRadius: "var(--radius-md)",
                      flexShrink: 0,
                      background: "var(--bg-surface-elevated)",
                      boxShadow: "0 8px 24px rgba(0, 0, 0, 0.35)",
                      border: "1px solid var(--border-color)",
                    }}
                  />
                ) : (
                  <div
                    style={{
                      width: "104px",
                      height: "104px",
                      borderRadius: "var(--radius-md)",
                      flexShrink: 0,
                      background: "var(--bg-surface-elevated)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      border: "1px solid var(--border-color)",
                    }}
                  >
                    <Icon name="music_note" size={44} style={{ opacity: 0.3 }} />
                  </div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="live-title" style={{ fontSize: "1.35rem", marginBottom: "4px" }}>
                    {currentTrack.title}
                  </div>
                  <div style={{ fontSize: "0.95rem", color: "var(--text-muted)", fontWeight: 600 }}>
                    {currentTrack.artist || t("radioLibrary.unknownArtist")}
                    {currentTrack.album ? ` — ${currentTrack.album}` : ""}
                  </div>
                </div>
              </div>

              <div className="live-progress">
                <span className="live-time">{formatTime(displayPosition)}</span>
                <input
                  type="range"
                  min={0}
                  max={duration || 0}
                  step={1}
                  value={displayPosition}
                  onChange={(e) => setSeekDragValue(Number(e.target.value))}
                  onMouseUp={(e) => {
                    const value = Number((e.target as HTMLInputElement).value);
                    sendCommand("radio_seek", { position_seconds: value });
                    setSeekDragValue(null);
                  }}
                  className="seek-slider"
                />
                <span className="live-time">{formatTime(duration)}</span>
              </div>

              <div className="live-controls">
                <button className="btn btn-secondary control-btn" onClick={() => sendCommand("stop")}>
                  <Icon name="stop" size={18} />
                  <span>{t("radioRemote.stop")}</span>
                </button>
                <button className="btn btn-secondary control-btn control-btn-icon" onClick={() => sendCommand("radio_previous_track")} title={t("radioRemote.previousTrack")}>
                  <Icon name="skip_previous" size={20} filled />
                </button>
                <button className="btn btn-primary control-btn control-btn-main" onClick={handlePlayPause}>
                  <Icon name={state.playing ? "pause" : "play_arrow"} size={22} filled />
                  <span>{state.playing ? t("radioRemote.pause") : t("radioRemote.play")}</span>
                </button>
                <button className="btn btn-secondary control-btn control-btn-icon" onClick={() => sendCommand("radio_next_track")} title={t("radioRemote.nextTrack")}>
                  <Icon name="skip_next" size={20} filled />
                </button>
                <button
                  className={`btn ${state.shuffle ? "btn-primary" : "btn-secondary"} control-btn control-btn-pill`}
                  onClick={() => sendCommand("radio_set_shuffle", { on: !state.shuffle })}
                  title={t("radioRemote.shuffleLabel")}
                >
                  <Icon name="shuffle" size={16} />
                  <span>Aléatoire</span>
                </button>
                <button
                  className={`btn ${state.repeat !== "off" ? "btn-primary" : "btn-secondary"} control-btn control-btn-pill`}
                  onClick={handleRepeatCycle}
                  title={repeatLabel}
                >
                  <Icon name={state.repeat === "track" ? "repeat_one" : "repeat"} size={16} />
                  <span>{repeatLabel}</span>
                </button>
              </div>

              <div className="volume-row">
                <span>{t("radioRemote.volume")}</span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={displayVolume}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    setVolumeDragValue(value);
                    sendCommand("volume", { volume: value });
                  }}
                  onMouseUp={() => setVolumeDragValue(null)}
                  className="volume-slider"
                />
                <span className="volume-value">{displayVolume}%</span>
                <div className="volume-presets">
                  {[25, 50, 75, 100].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      className={`volume-preset-btn ${displayVolume === preset ? "active" : ""}`}
                      onClick={() => {
                        setVolumeDragValue(preset);
                        sendCommand("volume", { volume: preset });
                        setTimeout(() => setVolumeDragValue(null), 100);
                      }}
                    >
                      {preset}%
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="live-empty">{t("radioRemote.emptyNowPlaying")}</div>
          )}
        </div>
      </div>

      <div className="dashboard-bento-grid" style={variant === "compact" ? { gridTemplateColumns: "1fr" } : undefined}>
        <div className="bento-col-main">
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
                  // Pochette du 1er morceau illustré, durée totale à droite : aperçu avant de lancer.
                  thumbnail: p.cover_track_id != null ? getApiUrl(`/radio/tracks/${p.cover_track_id}/cover`) : null,
                  square: true,
                  meta: formatDuration(p.total_duration_seconds),
                }))}
              />
              <button className="btn btn-primary" onClick={handleLaunch} disabled={!selectedPlaylistId}>
                <Icon name="play_arrow" size={16} filled />
                {t("radioRemote.launch")}
              </button>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "10px", fontSize: "0.85rem", color: "var(--text-muted)" }}>
              <input type="checkbox" checked={shuffleOnLoad} onChange={(e) => setShuffleOnLoad(e.target.checked)} />
              {t("radioRemote.shuffleOnLoad")}
            </label>
            {/* Lecture aléatoire de TOUTE la bibliothèque, sans playlist : indépendant du sélecteur ci-dessus. */}
            <button className="btn btn-secondary" style={{ width: "100%", marginTop: "12px" }} onClick={() => sendCommand("radio_shuffle_all")}>
              <Icon name="shuffle" size={16} />
              {t("radioRemote.shuffleAll")}
            </button>
            {playlists.length === 0 && <p className="live-empty" style={{ marginTop: "12px" }}>{t("radioRemote.noPlaylists")}</p>}
          </div>

          {/* Gestion du son de CETTE sortie : égaliseur, basses, préréglages. Appliqué par le
              lecteur de la sortie (graphe Web Audio), réglages persistés par sortie. */}
          <div className="live-block" style={{ marginTop: "16px" }}>
            <RadioSoundPanel sound={state.sound} sendCommand={sendCommand} variant={variant} />
          </div>
        </div>

        {variant === "full" && (
        <div className="bento-col-side">
          <div className="live-block">
            <div className="live-header">
              <h3>{t("radioRemote.queueTitle")}</h3>
              {queue.length > 0 && <span className="status-pill neutral">{queue.length}</span>}
            </div>
            {queue.length === 0 ? (
              <p className="live-empty">{t("radioRemote.queueEmpty")}</p>
            ) : (
              <>
                <p className="rq-summary">{t("radioRemote.queueSummary", { count: queue.length, duration: formatDuration(queueSeconds) })}</p>
                {/* Pochette, titre, artiste, style, durée de chaque morceau; glisser-déposer pour réordonner. */}
                <RadioQueueList
                  tracks={queue}
                  baseIndex={(state.index ?? -1) + 1}
                  getApiUrl={getApiUrl}
                  onRemove={(index) => sendCommand("radio_remove_from_queue", { index })}
                  onMove={(from, to) => sendCommand("radio_move_in_queue", { from_index: from, to_index: to })}
                />
              </>
            )}

            <h3 style={{ marginTop: "18px" }}>{t("radioRemote.addToQueueTitle")}</h3>
            {/* Recherche avec autocomplétion (titres, artistes, albums, styles des résultats) */}
            <SearchBox
              className="filter-select"
              value={queueSearch}
              onChange={setQueueSearch}
              suggestions={queueSuggestions}
              placeholder={t("radioRemote.addToQueueSearchPlaceholder")}
            />
            {queueSearch.trim() && (
              <div className="rq-results">
                {queueResults.length === 0 ? (
                  <p className="live-empty">{t("radioRemote.noSearchResults")}</p>
                ) : (
                  queueResults.map((track) => (
                    <div key={track.id} className="rq-row">
                      {track.has_cover ? (
                        // eslint-disable-next-line @next/next/no-img-element -- pochette servie par l'API locale, export statique
                        <img className="rq-cover" src={getApiUrl(`/radio/tracks/${track.id}/cover`)} alt="" loading="lazy" />
                      ) : (
                        <span className="rq-cover rq-cover--empty" aria-hidden="true">
                          <Icon name="music_note" size={20} style={{ opacity: 0.4 }} />
                        </span>
                      )}
                      <span className="rq-text">
                        <span className="rq-title">
                          <Highlight text={track.title} query={queueSearch} />
                        </span>
                        <span className="rq-sub">
                          <span className="rq-artist">
                            <Highlight text={track.artist || t("radioLibrary.unknownArtist")} query={queueSearch} />
                          </span>
                          {track.genre ? <span className="rq-genre">{track.genre}</span> : null}
                        </span>
                      </span>
                      <span className="rq-duration">{formatTime(track.duration_seconds)}</span>
                      <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                        <button
                          className="btn btn-secondary"
                          style={{ height: "30px", padding: "0 10px", fontSize: "0.75rem" }}
                          title={t("radioRemote.playNextHint")}
                          onClick={() => sendCommand("radio_play_next", { track_id: track.id })}
                        >
                          <Icon name="playlist_play" size={14} />
                          {t("radioRemote.playNext")}
                        </button>
                        <button
                          className="btn btn-secondary"
                          style={{ height: "30px", padding: "0 10px", fontSize: "0.75rem" }}
                          title={t("radioRemote.addToQueueHint")}
                          onClick={() => sendCommand("radio_add_to_queue", { track_id: track.id })}
                        >
                          <Icon name="add" size={14} />
                          {t("radioRemote.add")}
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
        )}
      </div>
    </>
  );
}
