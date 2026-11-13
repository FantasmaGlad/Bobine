"use client";

import ConfirmDialog from "@/components/ConfirmDialog";
import { useAppSettings } from "@/lib/AppSettingsContext";

import type { PlaylistEditor } from "./usePlaylistEditor";
import type { TrackEditor } from "./useTrackEditor";
import type { TrackSelection } from "./useTrackSelection";

const TEXT = { fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 } as const;

export default function RadioLibraryDialogs({ track, selection, playlist }: { track: TrackEditor; selection: TrackSelection; playlist: PlaylistEditor }) {
  const { t } = useAppSettings();
  const common = { confirmLabel: t("radioLibrary.confirmDelete"), cancelLabel: t("radioLibrary.cancel"), danger: true };
  return (
    <>
      {track.toDelete && (
        <ConfirmDialog {...common} title={t("radioLibrary.deleteConfirmTitle")} onConfirm={track.remove} onCancel={() => track.setToDelete(null)}>
          <p style={TEXT}>{t("radioLibrary.deleteConfirmText", { title: track.toDelete.title })}</p>
        </ConfirmDialog>
      )}
      {selection.confirmDelete && (
        <ConfirmDialog {...common} title={t("radioLibrary.bulkDeleteTitle", { count: selection.selected.size })} onConfirm={selection.remove} onCancel={() => selection.setConfirmDelete(false)}>
          <p style={TEXT}>{t("radioLibrary.bulkDeleteText")}</p>
        </ConfirmDialog>
      )}
      {playlist.toDelete && (
        <ConfirmDialog {...common} title={t("radioLibrary.deletePlaylist")} onConfirm={playlist.remove} onCancel={() => playlist.setToDelete(null)}>
          <p style={TEXT}>{t("radioLibrary.deletePlaylistConfirm", { name: playlist.toDelete.name })}</p>
        </ConfirmDialog>
      )}
    </>
  );
}
