"use client";

import { useRef, useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import type { TagEntry } from "./types";
import type { TrackEditor, TrackForm } from "./useTrackEditor";

interface Props {
  editor: TrackEditor;
  tags: TagEntry[];
  coverUrl: (id: number) => string;
}

function Field({ editor, name, label, type = "text", flex }: { editor: TrackEditor; name: keyof TrackForm; label: string; type?: string; flex?: boolean }) {
  const { t } = useAppSettings();
  return (
    <div className="form-group" style={flex ? { flex: 1 } : undefined}>
      <label className="form-label">{t(label)}</label>
      <input type={type} className="form-control" value={editor.form[name]} onChange={(e) => editor.setForm({ ...editor.form, [name]: e.target.value })} required={name === "title"} />
    </div>
  );
}

function TagChips({ editor, tags }: Omit<Props, "coverUrl">) {
  const { t } = useAppSettings();
  const [chip, setChip] = useState("");
  const add = () => {
    if (!chip.trim()) return;
    editor.addTag(chip.trim());
    setChip("");
  };
  const names = Array.from(new Set([...tags.map((tg) => tg.name), ...editor.tags])).sort((a, b) => a.localeCompare(b));
  return (
    <div className="form-group">
      <label className="form-label">{t("radioLibrary.fieldTags")}</label>
      <div className="rl-chips">
        {names.map((name) => {
          const on = editor.tags.includes(name);
          return (
            <button key={name} type="button" className={`rl-chip ${on ? "on" : ""}`} onClick={() => editor.toggleTag(name)}>
              {on && <Icon name="check" size={13} />} {name}
            </button>
          );
        })}
      </div>
      <div className="rl-chip-add">
        <input type="text" className="form-control" placeholder={t("radioLibrary.addTagPlaceholder")} value={chip}
          onChange={(e) => setChip(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <button type="button" className="btn btn-secondary" onClick={add}><Icon name="add" size={16} /></button>
      </div>
      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>{t("radioLibrary.tagsChipsHint")}</span>
    </div>
  );
}

function Cover({ editor, coverUrl }: Omit<Props, "tags">) {
  const { t } = useAppSettings();
  const input = useRef<HTMLInputElement>(null);
  const track = editor.track!;
  return (
    <div style={{ display: "flex", gap: "16px", alignItems: "flex-start", marginBottom: "16px" }}>
      <div style={{ width: "120px", height: "120px", flexShrink: 0, borderRadius: "8px", overflow: "hidden", background: "var(--bg-surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        {track.has_cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={coverUrl(track.id)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : <Icon name="music_note" size={36} style={{ opacity: 0.25 }} />}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "8px" }}>{t("radioLibrary.cover")}</div>
        <input ref={input} type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) editor.uploadCover(file);
          e.target.value = "";
        }} />
        <button type="button" className="btn btn-secondary" onClick={() => input.current?.click()}><Icon name="image" size={16} /> {t("radioLibrary.changeCover")}</button>
      </div>
    </div>
  );
}

export default function TrackDrawer({ editor, tags, coverUrl }: Props) {
  const { t } = useAppSettings();
  return (
    <>
      <div className="detail-drawer-overlay" onClick={editor.close} />
      <div className="detail-drawer">
        <div className="drawer-header">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", maxWidth: "80%" }}>{t("radioLibrary.editTitle")}</h3>
          <button className="close-btn" onClick={editor.close}><Icon name="close" size={20} /></button>
        </div>
        <div className="drawer-body">
          <Cover editor={editor} coverUrl={coverUrl} />
          <form className="drawer-form" onSubmit={editor.save}>
            <Field editor={editor} name="title" label="radioLibrary.fieldTitle" />
            <div style={{ display: "flex", gap: "12px" }}>
              <Field editor={editor} name="artist" label="radioLibrary.fieldArtist" flex />
              <Field editor={editor} name="album_artist" label="radioLibrary.fieldAlbumArtist" flex />
            </div>
            <Field editor={editor} name="album" label="radioLibrary.fieldAlbum" />
            <div style={{ display: "flex", gap: "12px" }}>
              <Field editor={editor} name="track_number" label="radioLibrary.fieldTrackNumber" type="number" flex />
              <Field editor={editor} name="disc_number" label="radioLibrary.fieldDiscNumber" type="number" flex />
              <Field editor={editor} name="year" label="radioLibrary.fieldYear" type="number" flex />
            </div>
            <Field editor={editor} name="genre" label="radioLibrary.fieldGenre" />
            <TagChips editor={editor} tags={tags} />
            <div className="drawer-actions">
              <button type="submit" className="btn btn-primary" style={{ flex: 1, height: "48px" }} disabled={editor.saving}>{editor.saving ? t("radioLibrary.saving") : t("radioLibrary.save")}</button>
              <button type="button" className="btn btn-danger" style={{ height: "48px" }} onClick={() => editor.setToDelete(editor.track)}>{t("radioLibrary.delete")}</button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
