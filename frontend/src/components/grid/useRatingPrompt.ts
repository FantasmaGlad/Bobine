import { useEffect, useRef, useState } from "react";

interface PlayingCourse {
  video_id?: number | null;
  title?: string | null;
  position_seconds: number;
  duration_seconds: number;
}

export function useRatingPrompt(nowPlaying: PlayingCourse | null) {
  const [ratingCourse, setRatingCourse] = useState<{
    videoId: number;
    title: string;
  } | null>(null);
  const ratingShownForVideoRef = useRef<number | null>(null);
  const lastPlayingRef = useRef<{
    videoId: number;
    title: string;
    position: number;
    duration: number;
  } | null>(null);

  useEffect(() => {
    if (nowPlaying && nowPlaying.video_id) {
      lastPlayingRef.current = {
        videoId: nowPlaying.video_id,
        title: nowPlaying.title || "",
        position: nowPlaying.position_seconds,
        duration: nowPlaying.duration_seconds,
      };

      if (
        nowPlaying.duration_seconds > 0 &&
        nowPlaying.position_seconds / nowPlaying.duration_seconds >= 0.95 &&
        ratingShownForVideoRef.current !== nowPlaying.video_id
      ) {
        ratingShownForVideoRef.current = nowPlaying.video_id;
        setRatingCourse({
          videoId: nowPlaying.video_id,
          title: nowPlaying.title || "",
        });
      }
    } else if (!nowPlaying && lastPlayingRef.current) {
      const last = lastPlayingRef.current;
      if (
        last.duration > 0 &&
        last.position / last.duration >= 0.90 &&
        ratingShownForVideoRef.current !== last.videoId
      ) {
        ratingShownForVideoRef.current = last.videoId;
        setRatingCourse({
          videoId: last.videoId,
          title: last.title,
        });
      }
      lastPlayingRef.current = null;
    }
  }, [nowPlaying]);
  return [ratingCourse, setRatingCourse] as const;
}
