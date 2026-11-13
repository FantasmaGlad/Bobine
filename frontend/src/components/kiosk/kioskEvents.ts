import { videoStreamUrl } from "@/lib/clientCodecSupport";
import { getApiUrl } from "@/lib/apiUrl";
import { formatTime } from "@/lib/format";
import { unloadMedia } from "@/lib/mediaElement";
import type { PlaybackEvent } from "@/lib/usePlaybackSocket";
import type { OsdContent } from "./media";

export interface KioskMedia {
  video: HTMLVideoElement | null;
  bgVideo: HTMLVideoElement | null;
  audio: HTMLAudioElement | null;
}

export interface KioskEventContext {
  isPrimary: () => boolean;
  lastSeekTime: () => number;
  tryPlay: (el: HTMLMediaElement | null | undefined) => void;
  showOsd: (content: OsdContent) => void;
  showVolumeHud: (state: { level: number; muted: boolean }) => void;
}

export function applyKioskEvent(evt: PlaybackEvent, media: KioskMedia, ctx: KioskEventContext): void {
    const { cause, data } = evt;
    const { video, bgVideo, audio } = media;

    const currentTrack =
      data.audio_tracks && data.audio_track_index !== null && data.audio_track_index !== undefined
        ? data.audio_tracks[data.audio_track_index]
        : null;
    const backgroundId = data.current_background?.id ?? data.current_audio_course?.background_id ?? null;
    const backgroundIsImage = data.current_background?.is_image ?? false;

    const applyVolume = (el: HTMLMediaElement) => {
      el.muted = false;
      el.volume = data.volume / 100;
    };

    const syncAudioToTrack = (resetTime: boolean) => {
      if (!audio || !currentTrack) return;
      const src = getApiUrl(`/audio/tracks/${currentTrack.id}/stream`);
      if (!audio.src || !audio.src.endsWith(src)) {
        audio.src = src;
        audio.load();
      }
      void resetTime;
      applyVolume(audio);
      if (!data.audio_playing) audio.pause();
    };

    const syncBackgroundLayer = () => {
      if (!bgVideo) return;
      if (!backgroundId || backgroundIsImage) {
        unloadMedia(bgVideo);
        return;
      }
      const bgSrc = getApiUrl(`/backgrounds/${backgroundId}/stream`);
      if (!bgVideo.src || !bgVideo.src.endsWith(bgSrc)) {
        bgVideo.src = bgSrc;
        bgVideo.load();
        if (data.audio_playing) bgVideo.play().catch(() => {});
      }
    };

    switch (cause) {
      case "sync": {
        if (!data.current_video) unloadMedia(video);
        if (!backgroundId || backgroundIsImage) unloadMedia(bgVideo);
        if (!data.current_audio_course) unloadMedia(audio);
        if (backgroundId && !backgroundIsImage && bgVideo) {
          const bgSrc = getApiUrl(`/backgrounds/${backgroundId}/stream`);
          if (!bgVideo.src || !bgVideo.src.endsWith(bgSrc)) bgVideo.src = bgSrc;
          if (!data.current_audio_course || data.audio_playing) bgVideo.play().catch(() => {});
          else bgVideo.pause();
        }
        if (data.current_audio_course && audio && currentTrack) {
          const aSrc = getApiUrl(`/audio/tracks/${currentTrack.id}/stream`);
          if (!audio.src || !audio.src.endsWith(aSrc)) {
            audio.src = aSrc;
            audio.load();
          }
          applyVolume(audio);
        }
        if (!video || !data.current_video) break;
        const src = videoStreamUrl(getApiUrl, data.current_video.id);
        applyVolume(video);
        const srcChanged = !video.src || !video.src.endsWith(src);
        if (srcChanged) {
          video.src = src;
          video.load();
        }
        break;
      }
      case "position_tick": {
        if (ctx.isPrimary()) break;
        if (Date.now() - ctx.lastSeekTime() < 3000) break;
        if (data.current_audio_course && audio && currentTrack) {
          if (bgVideo && bgVideo.src) {
            if (data.audio_playing && bgVideo.paused) ctx.tryPlay(bgVideo);
            else if (!data.audio_playing && !bgVideo.paused) bgVideo.pause();
          }
        }
        break;
      }
      case "load": {
        unloadMedia(bgVideo);
        unloadMedia(audio);
        if (!video || !data.current_video) break;
        video.src = videoStreamUrl(getApiUrl, data.current_video.id);
        applyVolume(video);
        video.load();
        break;
      }
      case "load_background": {
        unloadMedia(video);
        unloadMedia(audio);
        if (backgroundIsImage) {
          unloadMedia(bgVideo);
          break;
        }
        if (!bgVideo || !data.current_background) break;
        bgVideo.src = getApiUrl(`/backgrounds/${data.current_background.id}/stream`);
        bgVideo.load();
        bgVideo.play().catch(() => {});
        break;
      }
      case "load_audio_course":
      case "audio_set_background": {
        unloadMedia(video);
        syncBackgroundLayer();
        if (cause === "load_audio_course") syncAudioToTrack(true);
        break;
      }
      case "audio_next_track":
      case "audio_previous_track":
      case "audio_jump_to_track":
      case "audio_restart_track":
        syncBackgroundLayer();
        syncAudioToTrack(true);
        break;
      case "play":
        if (data.current_audio_course) {
          ctx.tryPlay(audio);
          if (bgVideo && bgVideo.src) ctx.tryPlay(bgVideo);
        }
        break;
      case "pause":
        if (data.current_audio_course) {
          audio?.pause();
          bgVideo?.pause();
        } else {
          video?.pause();
        }
        break;
      case "stop":
        unloadMedia(video);
        unloadMedia(bgVideo);
        unloadMedia(audio);
        break;
      case "seek":
        ctx.showOsd({
          icon: "fast_forward",
          label: `${formatTime(data.position_seconds)} / ${formatTime(data.current_video?.duration_seconds)}`,
        });
        break;
      case "volume":
        if (video) applyVolume(video);
        if (audio) applyVolume(audio);
        ctx.showVolumeHud({ level: data.volume / 100, muted: false });
        break;
      case "speed":
        ctx.showOsd({ icon: "speed", label: `${data.speed.toFixed(2)}x` });
        break;
      default:
        break;
    }
}
