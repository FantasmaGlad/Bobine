"use client";

import Icon from "@/components/Icon";
import { clampSeconds, type SignageEntry } from "@/lib/signageLoop";
import { thumbnailUrl } from "@/lib/thumbnail";
import type { VisualItem } from "@/components/visuals/useVisualLibrary";
import type { ReactNode } from "react";

type Translate = (key: string, vars?: Record<string, string | number>) => string;
type LoopVisual = Pick<VisualItem, "id" | "title" | "thumbnail_path" | "is_image">;

function Thumb({ visual }: { visual: LoopVisual | undefined }) {
  const src = thumbnailUrl(visual?.thumbnail_path);
  return <span className="signage-thumb">{src ? <img src={src} alt="" /> : <Icon name={visual?.is_image ? "image" : "movie"} size={18} />}</span>;
}

function LoopRow({ entry, index, last, visual, t, onMove, onSeconds, onRemove }: {
  entry: SignageEntry; index: number; last: boolean; visual: LoopVisual | undefined; t: Translate;
  onMove: (to: number) => void; onSeconds: (seconds: number | null) => void; onRemove: () => void;
}) {
  return (
    <li className="signage-row">
      <span className="signage-row__rank">{index + 1}</span>
      <Thumb visual={visual} />
      <span className="signage-row__title">{entry.title}</span>
      <label className="signage-row__seconds">
        <input
          type="number" className="form-control" min={2} max={3600} inputMode="numeric"
          defaultValue={entry.seconds ?? ""}
          placeholder={entry.is_image ? "10" : t("signage.wholeVideo")}
          aria-label={t("signage.secondsLabel", { title: entry.title })}
          onBlur={(e) => onSeconds(clampSeconds(e.target.value))}
        />
        <span>s</span>
      </label>
      <button type="button" className="btn btn-icon" disabled={index === 0} onClick={() => onMove(index - 1)} aria-label={t("signage.moveUp")}><Icon name="arrow_upward" size={18} /></button>
      <button type="button" className="btn btn-icon" disabled={last} onClick={() => onMove(index + 1)} aria-label={t("signage.moveDown")}><Icon name="arrow_downward" size={18} /></button>
      <button type="button" className="btn btn-icon" onClick={onRemove} aria-label={t("signage.remove")}><Icon name="close" size={18} /></button>
    </li>
  );
}

export default function LoopEditor({ entries, visuals, importAction, t, onMove, onSeconds, onRemove, onAdd }: {
  entries: SignageEntry[]; visuals: LoopVisual[]; importAction: ReactNode; t: Translate;
  onMove: (from: number, to: number) => void; onSeconds: (index: number, seconds: number | null) => void;
  onRemove: (index: number) => void; onAdd: (visualId: number) => void;
}) {
  const byId = new Map(visuals.map((visual) => [visual.id, visual]));
  return (
    <div className="signage-editor">
      <section className="live-block">
        <h3>{t("signage.loopTitle")}</h3>
        {entries.length === 0 ? <p className="signage-hint">{t("signage.loopEmpty")}</p> : (
          <ol className="signage-list">
            {entries.map((entry, index) => (
              <LoopRow key={`${index}-${entry.visual_id}-${entry.seconds}`} entry={entry} index={index} last={index === entries.length - 1}
                visual={byId.get(entry.visual_id)} t={t}
                onMove={(to) => onMove(index, to)} onSeconds={(seconds) => onSeconds(index, seconds)} onRemove={() => onRemove(index)} />
            ))}
          </ol>
        )}
      </section>
      <section className="live-block">
        <div className="signage-add-head">
          <h3>{t("signage.addTitle")}</h3>
          {importAction}
        </div>
        {visuals.length === 0 ? <p className="signage-hint">{t("signage.noVisuals")}</p> : (
          <ul className="signage-pick">
            {visuals.map((visual) => (
              <li key={visual.id}>
                <button type="button" className="signage-pick__item olc-press" onClick={() => onAdd(visual.id)}>
                  <Thumb visual={visual} />
                  <span>{visual.title}</span>
                  <Icon name="add" size={18} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
