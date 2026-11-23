"use client";

import Icon from "@/components/Icon";
import { clampSeconds, type SignageEntry } from "@/lib/signageLoop";
import type { BackgroundItem } from "@/components/backgrounds/types";
import { thumbnailUrl } from "@/lib/thumbnail";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

function Thumb({ background }: { background: BackgroundItem | undefined }) {
  const src = thumbnailUrl(background?.thumbnail_path);
  return <span className="signage-thumb">{src ? <img src={src} alt="" /> : <Icon name={background?.is_image ? "image" : "movie"} size={18} />}</span>;
}

function LoopRow({ entry, index, last, background, t, onMove, onSeconds, onRemove }: {
  entry: SignageEntry; index: number; last: boolean; background: BackgroundItem | undefined; t: Translate;
  onMove: (to: number) => void; onSeconds: (seconds: number | null) => void; onRemove: () => void;
}) {
  return (
    <li className="signage-row">
      <span className="signage-row__rank">{index + 1}</span>
      <Thumb background={background} />
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

export default function LoopEditor({ entries, backgrounds, t, onMove, onSeconds, onRemove, onAdd }: {
  entries: SignageEntry[]; backgrounds: BackgroundItem[]; t: Translate;
  onMove: (from: number, to: number) => void; onSeconds: (index: number, seconds: number | null) => void;
  onRemove: (index: number) => void; onAdd: (backgroundId: number) => void;
}) {
  const byId = new Map(backgrounds.map((bg) => [bg.id, bg]));
  return (
    <div className="signage-editor">
      <section className="live-block">
        <h3>{t("signage.loopTitle")}</h3>
        {entries.length === 0 ? <p className="signage-hint">{t("signage.loopEmpty")}</p> : (
          <ol className="signage-list">
            {entries.map((entry, index) => (
              <LoopRow key={`${index}-${entry.background_id}-${entry.seconds}`} entry={entry} index={index} last={index === entries.length - 1}
                background={byId.get(entry.background_id)} t={t}
                onMove={(to) => onMove(index, to)} onSeconds={(seconds) => onSeconds(index, seconds)} onRemove={() => onRemove(index)} />
            ))}
          </ol>
        )}
      </section>
      <section className="live-block">
        <h3>{t("signage.addTitle")}</h3>
        {backgrounds.length === 0 ? <p className="signage-hint">{t("signage.noBackgrounds")}</p> : (
          <ul className="signage-pick">
            {backgrounds.map((bg) => (
              <li key={bg.id}>
                <button type="button" className="signage-pick__item olc-press" onClick={() => onAdd(bg.id)}>
                  <Thumb background={bg} />
                  <span>{bg.title}</span>
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
