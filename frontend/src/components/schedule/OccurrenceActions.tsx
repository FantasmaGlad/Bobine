"use client";

import ResponsiveSelect from "@/components/ResponsiveSelect";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Occurrence } from "@/lib/scheduleTime";

import type { OccurrenceControls } from "./useOccurrenceControls";
import type { ScheduleCatalog } from "./useScheduleData";

interface Props {
  occurrence: Occurrence;
  occurrenceKey: string;
  controls: OccurrenceControls;
  catalog: ScheduleCatalog;
}

function replacementOptions(o: Occurrence, catalog: ScheduleCatalog, t: (key: string) => string) {
  if (o.target_type === "radio_playlist") {
    return catalog.radioPlaylists.map((p) => ({ value: `radio_playlist:${p.id}`, label: p.name, group: t("schedule.radioPlaylistsGroup") }));
  }
  return [
    ...catalog.videos.map((v) => ({ value: `video:${v.id}`, label: v.title, group: t("schedule.videosGroup") })),
    ...catalog.playlists.map((p) => ({ value: `playlist:${p.id}`, label: p.name, group: t("schedule.playlistsGroup") })),
  ];
}

function Replace({ occurrence, occurrenceKey, controls, catalog }: Props) {
  const { t } = useAppSettings();
  if (controls.replacingKey !== occurrenceKey) {
    return (
      <button type="button" className="btn btn-secondary" onClick={() => controls.startReplace(occurrenceKey)}>
        {t("schedule.replaceOccurrence")}
      </button>
    );
  }
  return (
    <>
      <ResponsiveSelect
        value={controls.replaceValue}
        onChange={controls.setReplaceValue}
        placeholder={t("schedule.replaceWith")}
        title={t("schedule.replaceWith")}
        style={{ width: "100%", minHeight: "26px", fontSize: "0.7rem" }}
        options={replacementOptions(occurrence, catalog, t)}
      />
      <button type="button" className="btn btn-primary" onClick={() => controls.replace(occurrence)}>
        {t("schedule.confirmReplace")}
      </button>
    </>
  );
}

export default function OccurrenceActions(props: Props) {
  const { t } = useAppSettings();
  const { occurrence: o, controls } = props;
  const cancelled = o.override_action === "cancelled";
  const replaced = o.override_action === "replaced";
  const recurring = o.schedule_type === "recurring";
  return (
    <div className="schedule-occurrence-actions" onClick={(e) => e.stopPropagation()}>
      <button type="button" className="btn btn-secondary" onClick={() => controls.edit(o.schedule_id)}>
        {t("schedule.editSeries")}
      </button>
      {recurring && !cancelled && !replaced && (
        <button type="button" className="btn btn-secondary" onClick={() => controls.cancel(o)}>
          {t("schedule.cancelOccurrence")}
        </button>
      )}
      {recurring && (cancelled || replaced) && (
        <button type="button" className="btn btn-secondary" onClick={() => controls.restore(o)}>
          {t("schedule.restoreOccurrence")}
        </button>
      )}
      {recurring && !cancelled && <Replace {...props} />}
    </div>
  );
}
