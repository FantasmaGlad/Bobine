"use client";

import ConfirmDialog from "@/components/ConfirmDialog";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { useAppSettings } from "@/lib/AppSettingsContext";

import type { Video } from "./types";

const TEXT = { fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 } as const;

export function DeleteVideoDialog({ video, onConfirm, onCancel }: { video: Video; onConfirm: () => void; onCancel: () => void }) {
  const { t } = useAppSettings();
  return (
    <ConfirmDialog title={t("library.deleteVideoTitle")} confirmLabel={t("library.confirmDelete")} cancelLabel={t("common.cancel")} onConfirm={onConfirm} onCancel={onCancel} danger>
      <p style={TEXT}>
        {t("library.deleteVideoConfirmBefore")}{" "}
        <strong style={{ color: "var(--text-main)" }}>{video.title}</strong>
        {t("library.deleteVideoConfirmAfter")}
      </p>
    </ConfirmDialog>
  );
}

export function BulkDeleteDialog({ count, onConfirm, onCancel }: { count: number; onConfirm: () => void; onCancel: () => void }) {
  const { t } = useAppSettings();
  return (
    <ConfirmDialog title={t("library.deleteBulkTitle", { count })} confirmLabel={t("library.confirmDelete")} cancelLabel={t("common.cancel")} onConfirm={onConfirm} onCancel={onCancel} danger>
      <p style={TEXT}>{t("library.deleteBulkConfirm")}</p>
    </ConfirmDialog>
  );
}

interface AddProps {
  count: number;
  playlists: { id: number; name: string }[];
  target: string;
  onTarget: (id: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function AddToPlaylistDialog({ count, playlists, target, onTarget, onConfirm, onCancel }: AddProps) {
  const { t } = useAppSettings();
  return (
    <ConfirmDialog title={t("library.addToPlaylistTitle", { count })} confirmLabel={t("library.add")} cancelLabel={t("common.cancel")} onConfirm={onConfirm} onCancel={onCancel} confirmDisabled={!target}>
      <ResponsiveSelect
        className="form-control"
        value={target}
        onChange={onTarget}
        placeholder={t("library.choosePlaylist")}
        title={t("library.choosePlaylist")}
        options={playlists.map((p) => ({ value: String(p.id), label: p.name }))}
      />
      {playlists.length === 0 && <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>{t("library.noPlaylistsHint")}</p>}
    </ConfirmDialog>
  );
}
