"use client";

import { useState } from "react";

import ChapterTicks from "@/components/ChapterTicks";
import SeekPreview from "@/components/SeekPreview";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { chapterIndexAt, type Chapter } from "@/lib/chapters";
import { formatTime } from "@/lib/format";
import type { Storyboard } from "@/lib/storyboard";
import type { SubtitleTrack } from "@/lib/subtitles";

interface Props {
  visible: boolean;
  playing: boolean;
  position: number;
  duration: number;
  chapters: Chapter[];
  board: Storyboard | null;
  scrubbing: boolean;
  subtitles: SubtitleTrack[];
  activeSubtitle: number | "off";
  onSubtitle: (id: number | "off") => void;
  onPlayPause: () => void;
  onBack: () => void;
  onDrag: (value: number) => void;
  onSeek: (value: number) => void;
}

function SubtitleMenu({ subtitles, activeSubtitle, onSubtitle }: Pick<Props, "subtitles" | "activeSubtitle" | "onSubtitle">) {
  const { t } = useAppSettings();
  const [open, setOpen] = useState(false);
  const option = (id: number | "off", label: string) => (
    <button key={id} type="button" className={`cinema-subtitle-option ${activeSubtitle === id ? "active" : ""}`} onClick={() => { onSubtitle(id); setOpen(false); }}>
      <span>{label}</span>
      {activeSubtitle === id && <Icon name="check" size={16} />}
    </button>
  );
  return (
    <div className="cinema-subtitle-menu-wrap">
      <button type="button" className={`cinema-ctl-btn cinema-ctl-round ${activeSubtitle !== "off" ? "active" : ""}`} onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }} title={t("cinema.subtitles")}>
        <Icon name="subtitles" size={24} />
      </button>
      {open && (
        <div className="cinema-subtitle-popover" onClick={(e) => e.stopPropagation()}>
          <div className="cinema-subtitle-header">{t("cinema.subtitles")}</div>
          {option("off", t("cinema.subtitlesOff"))}
          {subtitles.map((sub) => option(sub.id, sub.language_label))}
        </div>
      )}
    </div>
  );
}

export default function CinemaControls(props: Props) {
  const { t } = useAppSettings();
  const { visible, playing, position, duration, chapters, board, scrubbing, subtitles, onPlayPause, onBack, onDrag, onSeek } = props;
  const chapter = chapterIndexAt(chapters, position);
  const release = (e: { target: EventTarget }) => onSeek(Number((e.target as HTMLInputElement).value));
  return (
    <div className={`cinema-controls ${visible ? "visible" : ""}`}>
      <div className="cinema-controls-top">
        <button className="cinema-ctl-btn" onClick={onBack} title={t("cinema.backToMenu")}>
          <Icon name="arrow_back" size={26} />
          <span>{t("cinema.backToMenu")}</span>
        </button>
      </div>
      <div className="cinema-controls-bottom">
        <div className="cinema-timeline">
        <span className="cinema-time">{formatTime(position)}</span>
        <div className="chapter-seek">
          <input type="range" className="cinema-seek" min={0} max={duration || 0} step={1} value={Math.min(position, duration || 0)}
            onChange={(e) => onDrag(Number(e.target.value))} onMouseUp={release} onTouchEnd={release} style={{ accentColor: "var(--accent-primary)" }} />
          <ChapterTicks chapters={chapters} duration={duration} />
          {scrubbing && duration > 0 && (
            <SeekPreview ratio={Math.min(1, Math.max(0, position / duration))} seconds={position} title={chapter >= 0 ? chapters[chapter].title : ""} board={board} />
          )}
        </div>
        <span className="cinema-time">{formatTime(duration)}</span>
        </div>
        <div className="cinema-controls-row">
          <button className="cinema-ctl-btn cinema-ctl-round" onClick={onPlayPause} title={playing ? t("cinema.pause") : t("cinema.play")}>
            <Icon name={playing ? "pause" : "play_arrow"} size={30} filled />
          </button>
          {subtitles.length > 0 && <SubtitleMenu {...props} />}
        </div>
      </div>
    </div>
  );
}
