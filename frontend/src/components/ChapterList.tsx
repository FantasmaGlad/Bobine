"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { chapterIndexAt, type Chapter } from "@/lib/chapters";
import { formatClock } from "@/lib/courseMeta";

interface ChapterListProps {
  chapters: Chapter[];
  position: number;
  onSeek: (seconds: number) => void;
  className?: string;
}

/** Chapitres du cours en cours : toucher une ligne y amène la lecture. Replié par défaut. */
export default function ChapterList({ chapters, position, onSeek, className = "" }: ChapterListProps) {
  const { t } = useAppSettings();
  const [open, setOpen] = useState(false);
  if (chapters.length === 0) return null;
  const current = chapterIndexAt(chapters, position);

  return (
    <div className={`chapter-list ${className}`.trim()}>
      <button type="button" className="chapter-list__toggle olc-press" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="chapter-list__title">
          <Icon name="format_list_numbered" size={18} />
          {t("chapters.title")}
          <span className="chapter-list__count">{chapters.length}</span>
        </span>
        <span className="chapter-list__current">{current >= 0 ? chapters[current].title : ""}</span>
        <Icon name={open ? "expand_less" : "expand_more"} size={20} />
      </button>
      {open && (
        <ol className="chapter-list__items">
          {chapters.map((chapter, index) => (
            <li key={chapter.id}>
              <button type="button" className={`chapter-list__item olc-press${index === current ? " is-current" : ""}`} onClick={() => onSeek(chapter.start_seconds)}>
                <span className="chapter-list__time">{formatClock(chapter.start_seconds)}</span>
                <span className="chapter-list__name">{chapter.title}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
