"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import SelectionBar from "./SelectionBar";
import { TrackCard, TrackRow } from "./TrackItems";
import TracksToolbar from "./TracksToolbar";
import type { RadioTrack } from "./types";
import type { RadioCatalog } from "./useRadioCatalog";
import type { TrackFilter } from "./useTrackFilter";
import type { TrackSelection } from "./useTrackSelection";
import { useViewMode } from "./useViewMode";

interface Props {
  catalog: RadioCatalog;
  filter: TrackFilter;
  selection: TrackSelection;
  onOpen: (track: RadioTrack) => void;
  onImport: () => void;
}

function Listing({ catalog, filter, selection, onOpen, onImport, grid }: Props & { grid: boolean }) {
  const { t } = useAppSettings();
  if (catalog.loading) return <div className="rl-center-note">{t("radioLibrary.loading")}</div>;
  if (catalog.tracks.length === 0) {
    return (
      <div className="rl-empty-state">
        <Icon name="radio" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
        <p style={{ margin: 0, fontWeight: 600 }}>{t("radioLibrary.empty")}</p>
        <button type="button" className="btn btn-primary" style={{ marginTop: "12px" }} onClick={onImport}><Icon name="cloud_upload" size={16} /> {t("radioLibrary.importButton")}</button>
      </div>
    );
  }
  if (filter.sorted.length === 0) return <div className="rl-center-note">{t("radioLibrary.noResults")}</div>;
  const Item = grid ? TrackCard : TrackRow;
  return (
    <div className={grid ? "videos-grid rl-grid" : "rl-list"}>
      {filter.sorted.map((track) => (
        <Item key={track.id} track={track} selected={selection.selected.has(track.id)} coverUrl={catalog.coverUrl} onOpen={() => onOpen(track)} onToggle={() => selection.toggle(track.id)} />
      ))}
    </div>
  );
}

export default function TracksSection(props: Props) {
  const { catalog, filter, selection } = props;
  const [viewMode, setViewMode] = useViewMode();
  const ids = filter.sorted.map((tr) => tr.id);
  const allSelected = ids.length > 0 && ids.every((id) => selection.selected.has(id));
  return (
    <>
      {selection.selected.size === 0 ? (
        <TracksToolbar filter={filter} viewMode={viewMode} onViewMode={setViewMode} allSelected={allSelected} onToggleAll={() => selection.toggleAll(ids)} />
      ) : (
        <SelectionBar selection={selection} tags={catalog.tags} playlists={catalog.playlists} />
      )}
      <Listing {...props} grid={viewMode === "grid"} />
    </>
  );
}
