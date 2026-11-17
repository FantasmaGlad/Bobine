"use client";

import React from "react";
import Icon from "@/components/Icon";
import PlaylistList from "@/components/PlaylistList";
import type { ToastState } from "@/lib/useToast";
import PlaylistDeleteDialog from "./PlaylistDeleteDialog";
import PlaylistForm from "./PlaylistForm";
import type { Translate } from "./types";
import type { PlaylistEditor } from "./usePlaylistEditor";

interface PlaylistEditorLayoutProps<Item> {
  editor: PlaylistEditor<Item>;
  prefix: "playlists" | "audioPlaylists";
  placeholderIcon: string;
  t: Translate;
  isMobile: boolean;
  loading: boolean;
  toast: ToastState | null;
  totalDurationSeconds: number;
  statusOnMobile: boolean;
  onLaunch: (e: React.MouseEvent, id: number) => void;
  sequencer: React.ReactNode;
  picker: React.ReactNode;
}

const TOAST_ICONS = { success: ["check_circle", "var(--accent-success-text)"], error: ["error", "var(--accent-error-text)"], warning: ["warning", "var(--accent-warning-text)"] } as const;

function Placeholder({ icon, prefix, t }: { icon: string; prefix: string; t: Translate }) {
  return (
    <div className="editor-placeholder">
      <Icon name={icon} size={48} color="var(--border-focus)" style={{ marginBottom: "12px" }} />
      <h4 style={{ margin: 0, fontWeight: 700, color: "var(--text-main)" }}>{t(`${prefix}.editorTitle`)}</h4>
      <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>{t(`${prefix}.editorPlaceholderHint`)}</p>
    </div>
  );
}

export default function PlaylistEditorLayout<Item>(props: PlaylistEditorLayoutProps<Item>) {
  const { editor, prefix, placeholderIcon, t, isMobile, loading, toast, onLaunch } = props;
  const { draft } = editor;
  const toastIcon = toast ? TOAST_ICONS[toast.type] : null;
  return (
    <div className="playlist-manager-wrap">
      {toast && (
        <div className={`toast ${toast.type}`}>
          {toastIcon && <Icon name={toastIcon[0]} size={20} color={toastIcon[1]} filled />}
          <span>{toast.message}</span>
        </div>
      )}
      <div className="playlists-split-container" style={isMobile ? { flexDirection: "column", height: "auto", overflow: "visible" } : undefined}>
        <PlaylistList
          prefix={prefix} t={t} isMobile={isMobile} loading={loading} playlists={editor.playlists}
          selectedPlaylistId={draft.selectedPlaylistId} isCreating={draft.isCreating}
          handleCreateOpen={draft.openCreate} handleSelectPlaylist={draft.select}
          handleLaunch={onLaunch} handleDuplicate={editor.duplicate} triggerDelete={editor.askDelete}
        />
        <div className="playlists-right-panel" style={isMobile ? { minWidth: 0, height: "auto", overflow: "visible" } : undefined}>
          {draft.selectedPlaylistId === null && !draft.isCreating
            ? <Placeholder icon={placeholderIcon} prefix={prefix} t={t} />
            : <PlaylistForm {...props} />}
        </div>
      </div>
      {editor.playlistToDelete && (
        <PlaylistDeleteDialog prefix={prefix} t={t} name={editor.playlistToDelete.name} onConfirm={editor.confirmDelete} onCancel={editor.cancelDelete} />
      )}
    </div>
  );
}

export type { PlaylistEditorLayoutProps };
