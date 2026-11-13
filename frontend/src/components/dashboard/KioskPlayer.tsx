"use client";

import { useState } from "react";

import ChapterList from "@/components/ChapterList";
import ChapterTicks from "@/components/ChapterTicks";
import Icon from "@/components/Icon";
import SubtitlePicker from "@/components/SubtitlePicker";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { useVideoChapters } from "@/lib/chapters";
import { formatTime } from "@/lib/format";
import type { PlaybackState } from "@/lib/usePlaybackSocket";

import { THUMB_STYLE, type Send } from "./types";

const SPEED_OPTIONS = [0.5, 1, 1.25, 1.5, 2];
const VOLUME_PRESETS = [25, 50, 75, 100];

interface Props {
  state: PlaybackState;
  livePosition: number;
  backgroundThumb: string | null;
  sendCommand: Send;
}

function NowPlaying({ state, backgroundThumb }: Pick<Props, "state" | "backgroundThumb">) {
  const { t } = useAppSettings();
  const background = state.state === "background";
  const thumb = background ? backgroundThumb : state.current_video?.thumbnail_url ? getApiUrl(`/thumbnails/${state.current_video.thumbnail_url}`) : null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
      {thumb ? <img src={thumb} alt="" style={THUMB_STYLE} /> : background && (
        <div style={{ width: "88px", height: "50px", borderRadius: "var(--radius-sm)", background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Icon name="wallpaper" size={22} style={{ opacity: 0.5 }} />
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <div className="live-title">{state.current_video?.title || (background ? state.current_background?.title : "")}</div>
        {background && <span style={{ fontSize: "0.8rem", color: "var(--accent-text)", fontWeight: 700 }}>{t("dashboard.ambianceActive")}</span>}
      </div>
    </div>
  );
}

function Controls({ state, sendCommand }: Pick<Props, "state" | "sendCommand">) {
  const { t } = useAppSettings();
  const background = state.state === "background";
  const playing = state.state === "playing";
  return (
    <div className="live-controls">
      <button className="btn btn-secondary control-btn" onClick={() => sendCommand("stop")}>
        <Icon name="stop" size={18} />
        {background ? t("dashboard.quitAmbiance") : t("dashboard.stop")}
      </button>
      {!background && (
        <>
          <button className="btn btn-primary control-btn control-btn-main" onClick={() => sendCommand(playing ? "pause" : "play")}>
            <Icon name={playing ? "pause" : "play_arrow"} size={20} filled />
            {playing ? t("dashboard.pause") : t("dashboard.play")}
          </button>
          <div className="speed-group">
            {SPEED_OPTIONS.map((s) => (
              <button key={s} className={`speed-btn ${state.speed === s ? "active" : ""}`} onClick={() => sendCommand("speed", { speed: s })}>{s}x</button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Volume({ state, sendCommand }: Pick<Props, "state" | "sendCommand">) {
  const { t } = useAppSettings();
  const [drag, setDrag] = useState<number | null>(null);
  const volume = drag ?? state.volume;
  return (
    <div className="volume-row">
      <span>{t("dashboard.volume")}</span>
      <input type="range" min={0} max={100} step={1} value={volume} className="volume-slider" onMouseUp={() => setDrag(null)}
        onChange={(e) => {
          const value = Number(e.target.value);
          setDrag(value);
          sendCommand("volume", { volume: value });
        }} />
      <span className="volume-value">{volume}%</span>
      <div className="volume-presets">
        {VOLUME_PRESETS.map((preset) => (
          <button key={preset} type="button" className={`volume-preset-btn olc-press ${volume === preset ? "active" : ""}`} onClick={() => sendCommand("volume", { volume: preset })}>{preset}%</button>
        ))}
      </div>
    </div>
  );
}

function Timeline({ state, livePosition, sendCommand }: Omit<Props, "backgroundThumb">) {
  const [drag, setDrag] = useState<number | null>(null);
  const chapters = useVideoChapters(state.current_video?.id, getApiUrl);
  const duration = state.current_video?.duration_seconds ?? 0;
  const position = drag ?? livePosition;
  const seek = (seconds: number) => sendCommand("seek", { position_seconds: seconds });
  return (
    <>
      <div className="live-progress">
        <span className="live-time">{formatTime(position)}</span>
        <div className="chapter-seek">
          <input type="range" min={0} max={duration || 0} step={1} value={position} className="seek-slider" onChange={(e) => setDrag(Number(e.target.value))}
            onMouseUp={(e) => {
              seek(Number((e.target as HTMLInputElement).value));
              setDrag(null);
            }} />
          <ChapterTicks chapters={chapters} duration={duration} />
        </div>
        <span className="live-time">{formatTime(duration)}</span>
      </div>
      {state.current_video && (
        <SubtitlePicker videoId={state.current_video.id} subtitle={state.subtitle} getApiUrl={getApiUrl} onChange={(subtitle) => sendCommand("set_subtitle", { subtitle })} className="subtitle-picker--inline" />
      )}
      <ChapterList chapters={chapters} position={position} onSeek={seek} className="chapter-list--inline" />
    </>
  );
}

export default function KioskPlayer(props: Props) {
  return (
    <>
      <NowPlaying {...props} />
      {props.state.state !== "background" && <Timeline {...props} />}
      <Controls {...props} />
      <Volume {...props} />
    </>
  );
}
