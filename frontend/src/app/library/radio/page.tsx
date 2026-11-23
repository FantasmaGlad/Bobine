"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import ArtistsSection from "@/components/radio-library/ArtistsSection";
import { fetchJson } from "@/components/radio-library/api";
import ImportSection from "@/components/radio-library/ImportSection";
import PlaylistDrawer from "@/components/radio-library/PlaylistDrawer";
import PlaylistsSection from "@/components/radio-library/PlaylistsSection";
import RadioLibraryDialogs from "@/components/radio-library/RadioLibraryDialogs";
import TagsSection from "@/components/radio-library/TagsSection";
import TrackDrawer from "@/components/radio-library/TrackDrawer";
import TracksSection from "@/components/radio-library/TracksSection";
import type { Filter, PlaylistDetail, PlaylistSummary, Section } from "@/components/radio-library/types";
import { usePlaylistEditor } from "@/components/radio-library/usePlaylistEditor";
import { useRadioCatalog } from "@/components/radio-library/useRadioCatalog";
import { useRadioImport } from "@/components/radio-library/useRadioImport";
import { useTrackEditor } from "@/components/radio-library/useTrackEditor";
import { useTrackFilter } from "@/components/radio-library/useTrackFilter";
import { useTrackSelection } from "@/components/radio-library/useTrackSelection";
import SegmentedTabs from "@/components/SegmentedTabs";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useToast } from "@/lib/useToast";

export default function RadioLibraryPage() {
  const { t } = useAppSettings();
  const [section, setSection] = useState<Section>("tracks");
  const { toast, showToast } = useToast();
  const catalog = useRadioCatalog();
  const filter = useTrackFilter(catalog.tracks);
  const selection = useTrackSelection(catalog.tracks, showToast, catalog.refreshAll);
  const importer = useRadioImport(showToast);
  const track = useTrackEditor(catalog, showToast);
  const playlist = usePlaylistEditor(catalog, showToast);

  const applyFilter = (next: Filter) => {
    filter.apply(next);
    setSection("tracks");
  };

  const showPlaylistTracks = async (summary: PlaylistSummary) => {
    const detail = await fetchJson<PlaylistDetail | null>(`/radio/playlists/${summary.id}`, null);
    if (!detail) return showToast(t("radioLibrary.playlistError"), "error");
    filter.apply({ type: "playlist", value: summary.name }, new Set(detail.items.map((i) => i.track.id)));
    setSection("tracks");
  };

  const tabs = [
    { id: "tracks", icon: "library_music", label: t("radioLibrary.sectionTracks"), count: catalog.tracks.length },
    { id: "playlists", icon: "queue_music", label: t("radioLibrary.sectionPlaylists"), count: catalog.playlists.length },
    { id: "artists", icon: "person", label: t("radioLibrary.sectionArtists"), count: catalog.artists.length },
    { id: "tags", icon: "label", label: t("radioLibrary.sectionTags"), count: catalog.tags.length + filter.genres.length },
    { id: "import", icon: "cloud_upload", label: t("radioLibrary.sectionImport") },
  ];

  return (
    <div className="radio-lib radio-lib--tabs">
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      <div className="live-block channel-card rl-nav-card">
        <div className="channel-card-left">
          <h3><Icon name="library_music" size={18} />{t("radioLibrary.title")}</h3>
          <span className="status-pill neutral">{t("radioLibrary.countLabel", { count: catalog.tracks.length })}</span>
        </div>
        <div className="channel-card-right">
          <SegmentedTabs ariaLabel={t("radioLibrary.sectionsLabel")} value={section} onChange={(id) => setSection(id as Section)} tabs={tabs} />
        </div>
      </div>
      <main className="radio-lib-main" onDragEnter={importer.onDrag} onDragOver={importer.onDrag} onDragLeave={importer.onDrag} onDrop={importer.onDrop}>
        {importer.dragActive && <div className="rl-drop-overlay"><Icon name="cloud_upload" size={40} /><span>{t("radioLibrary.dropHere")}</span></div>}
        {section === "tracks" && <TracksSection catalog={catalog} filter={filter} selection={selection} onOpen={track.open} onImport={() => setSection("import")} />}
        {section === "playlists" && <PlaylistsSection catalog={catalog} outputDefaults={playlist.outputDefaults} onCreate={playlist.create} onOpen={playlist.open} onShowTracks={showPlaylistTracks} />}
        {section === "artists" && <ArtistsSection catalog={catalog} onFilter={applyFilter} />}
        {section === "tags" && <TagsSection catalog={catalog} filter={filter} showToast={showToast} onFilter={applyFilter} />}
        {section === "import" && <ImportSection importer={importer} />}
      </main>
      {selection.menu && <div className="rl-popover-scrim" onClick={() => selection.setMenu(null)} />}
      {track.track && <TrackDrawer editor={track} tags={catalog.tags} coverUrl={catalog.coverUrl} />}
      {playlist.playlist && <PlaylistDrawer editor={playlist} playlist={playlist.playlist} tracks={catalog.tracks} suggestions={filter.suggestions} coverUrl={catalog.coverUrl} />}
      <RadioLibraryDialogs track={track} selection={selection} playlist={playlist} />
    </div>
  );
}
