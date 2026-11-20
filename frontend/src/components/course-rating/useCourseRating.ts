import { useCallback, useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";

interface Options {
  videoId: number;
  channel: "cable" | "network";
  duration: number;
  isCinemaMode: boolean;
  onClose?: () => void;
  onRated?: (score: number) => void;
}

function useCountdown(duration: number, submitted: boolean, onCloseRef: React.RefObject<(() => void) | undefined>) {
  const [remainingSeconds, setRemainingSeconds] = useState(duration);
  const startTimeRef = useRef<number>(0);
  useEffect(() => {
    if (submitted) return;
    startTimeRef.current = Date.now();
    const timer = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      const left = Math.max(0, duration - elapsed);
      setRemainingSeconds(left);
      if (left <= 0) {
        clearInterval(timer);
        if (onCloseRef.current) onCloseRef.current();
      }
    }, 100);
    return () => clearInterval(timer);
  }, [duration, submitted, onCloseRef]);
  return remainingSeconds;
}

async function postRating(videoId: number, score: number, channel: string, isCinemaMode: boolean) {
  try {
    await fetch(getApiUrl("/metrics/ratings"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: videoId, rating: score, channel, source: isCinemaMode ? "cinema" : "grid" }),
    });
  } catch (err) {
    console.error("Failed to submit rating:", err);
  }
}

export function useCourseRating({ videoId, channel, duration, isCinemaMode, onClose, onRated }: Options) {
  const [selectedScore, setSelectedScore] = useState<number | null>(null);
  const [hoveredScore, setHoveredScore] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  const remainingSeconds = useCountdown(duration, submitted, onCloseRef);

  const handleSelectScore = useCallback(async (score: number) => {
    if (submitted) return;
    setSelectedScore(score);
    setSubmitted(true);
    await postRating(videoId, score, channel, isCinemaMode);
    if (onRated) onRated(score);
    setTimeout(() => {
      if (onCloseRef.current) onCloseRef.current();
    }, 2500);
  }, [videoId, channel, isCinemaMode, submitted, onRated]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (onCloseRef.current) onCloseRef.current();
      } else if (e.key === "ArrowLeft") {
        setHoveredScore((prev) => Math.max(1, (prev || 1) - 1));
      } else if (e.key === "ArrowRight") {
        setHoveredScore((prev) => Math.min(5, (prev || 1) + 1));
      } else if ((e.key === "Enter" || e.key === " ") && hoveredScore && !submitted) {
        handleSelectScore(hoveredScore);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [hoveredScore, submitted, handleSelectScore]);

  return { selectedScore, hoveredScore, setHoveredScore, submitted, remainingSeconds, handleSelectScore };
}
