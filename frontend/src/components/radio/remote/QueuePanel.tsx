"use client";

import React, { useEffect, useMemo, useState } from "react";
import RadioQueueList from "@/components/RadioQueueList";
import SearchBox from "@/components/SearchBox";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMinutes } from "@/lib/format";
import { rankByQuery } from "@/lib/searchText";
import type { RadioState } from "@/lib/useRadioSocket";
import QueueSearchResult from "./QueueSearchResult";
import type { RadioTrackSearchResult, SendRadioCommand } from "./types";

function useTrackSearch() {
  const [allTracks, setAllTracks] = useState<RadioTrackSearchResult[]>([]);
  const [query, setQuery] = useState("");
  useEffect(() => {
    fetch(getApiUrl("/radio/tracks"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setAllTracks)
      .catch(() => setAllTracks([]));
  }, []);
  const results = useMemo(
    () =>
      query.trim()
        ? rankByQuery(allTracks, query, (track) => `${track.title} ${track.artist ?? ""} ${track.album ?? ""} ${track.genre ?? ""}`).slice(0, 8)
        : [],
    [allTracks, query],
  );
  const suggestions = useMemo(
    () => allTracks.flatMap((track) => [track.title, track.artist, track.album, track.genre].filter((x): x is string => !!x)),
    [allTracks],
  );
  return { query, setQuery, results, suggestions };
}

export default function QueuePanel({ state, sendCommand }: { state: RadioState; sendCommand: SendRadioCommand }) {
  const { t } = useAppSettings();
  const { query, setQuery, results, suggestions } = useTrackSearch();
  const queue = state.index !== null ? state.order.slice(state.index + 1) : [];
  const queueSeconds = queue.reduce((total, track) => total + (track.duration_seconds ?? 0), 0);
  return (
    <div className="live-block">
      <div className="live-header">
        <h3>{t("radioRemote.queueTitle")}</h3>
        {queue.length > 0 && <span className="status-pill neutral">{queue.length}</span>}
      </div>
      {queue.length === 0 ? (
        <p className="live-empty">{t("radioRemote.queueEmpty")}</p>
      ) : (
        <>
          <p className="rq-summary">{t("radioRemote.queueSummary", { count: queue.length, duration: formatMinutes(queueSeconds, "0 min") })}</p>
          <RadioQueueList
            tracks={queue}
            baseIndex={(state.index ?? -1) + 1}
            getApiUrl={getApiUrl}
            onRemove={(index) => sendCommand("radio_remove_from_queue", { index })}
            onMove={(from, to) => sendCommand("radio_move_in_queue", { from_index: from, to_index: to })}
          />
        </>
      )}
      <h3 style={{ marginTop: "18px" }}>{t("radioRemote.addToQueueTitle")}</h3>
      <SearchBox
        className="filter-select"
        value={query}
        onChange={setQuery}
        suggestions={suggestions}
        placeholder={t("radioRemote.addToQueueSearchPlaceholder")}
      />
      {query.trim() && (
        <div className="rq-results">
          {results.length === 0 ? (
            <p className="live-empty">{t("radioRemote.noSearchResults")}</p>
          ) : (
            results.map((track) => <QueueSearchResult key={track.id} track={track} query={query} sendCommand={sendCommand} />)
          )}
        </div>
      )}
    </div>
  );
}
