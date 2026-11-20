"use client";

import { useEffect, useMemo, useState } from "react";
import Icon from "@/components/Icon";
import { layoutOrbits, neighborhood, type Topology } from "@/lib/deviceMap";
import { type SectionProps } from "./shared/section";
import { useDevicesResource } from "./shared/useDevicesResource";
import MapGraph from "./map/MapGraph";
import MapLegend from "./map/MapLegend";
import MapPanel, { type OpenTab } from "./map/MapPanel";
import { nodeLabel } from "./map/mapText";
import { useMapViewport, type MapViewport } from "./map/useMapViewport";

interface Props extends Pick<SectionProps, "refreshKey" | "t"> {
  onOpen: OpenTab;
}

function MapControls({ viewport, t }: { viewport: MapViewport; t: SectionProps["t"] }) {
  return (
    <div className="dv-map-controls">
      <button type="button" className="dv-map-btn" aria-label={t("devices.map.zoomIn")} onClick={() => viewport.zoomCenter(1.25, true)}><Icon name="add" size={18} /></button>
      <button type="button" className="dv-map-btn" aria-label={t("devices.map.zoomOut")} onClick={() => viewport.zoomCenter(0.8, true)}><Icon name="remove" size={18} /></button>
      <button type="button" className="dv-map-btn" aria-label={t("devices.map.recenter")} onClick={viewport.recenter}><Icon name="center_focus_strong" size={18} /></button>
    </div>
  );
}

function mapKeyHandler(viewport: MapViewport, setSelected: (id: string | null) => void) {
  return (event: React.KeyboardEvent) => {
    if (event.key === "+" || event.key === "=" || event.key === "-") viewport.markInteracted();
    if (event.key === "Escape") setSelected(null);
    else if (event.key === "+" || event.key === "=") viewport.zoomCenter(1.2, false);
    else if (event.key === "-") viewport.zoomCenter(1 / 1.2, false);
    else if (event.key === "0") viewport.recenter();
  };
}

export default function MapSection({ refreshKey, t, onOpen }: Props) {
  const { data, error, loading, reload } = useDevicesResource<Topology>("/topology", refreshKey);
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  useEffect(() => {
    const timer = setInterval(() => { void reload(); }, 15000);
    return () => clearInterval(timer);
  }, [reload]);
  const layout = useMemo(() => (data ? layoutOrbits(data) : null), [data]);
  const viewport = useMapViewport(layout);
  const { view, size, frameRef } = viewport;

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error || !data || !layout) return <div className="rl-center-note">{t("devices.errors.generic")}</div>;

  const focusId = hover ?? selected;
  const near = focusId ? neighborhood(data.links, focusId) : null;
  const selectedNode = layout.nodes.find((n) => n.id === selected) ?? null;

  return (
    <div className="dv-map-wrap">
      <MapLegend counts={data.counts} t={t} />
      <div className="dv-map-frame" ref={frameRef} tabIndex={0} onKeyDown={mapKeyHandler(viewport, setSelected)} aria-label={t("devices.map.title")}>
        <svg
          className="dv-map"
          width={size.width}
          height={size.height}
          onPointerDown={viewport.onPointerDown}
          onPointerMove={viewport.onPointerMove}
          onPointerUp={viewport.onPointerUp}
          onPointerCancel={viewport.onPointerUp}
          onClick={() => { if (!viewport.dragged.current) setSelected(null); }}
        >
          <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
            <MapGraph layout={layout} near={near} selected={selected} setSelected={setSelected} setHover={setHover} t={t} />
          </g>
        </svg>
        <MapControls viewport={viewport} t={t} />
        {selectedNode && <MapPanel node={selectedNode} label={nodeLabel(selectedNode, t)} topology={data} t={t} onClose={() => setSelected(null)} onOpen={onOpen} />}
        {data.nodes.length <= 1 && <p className="dv-map-empty">{t("devices.map.empty")}</p>}
      </div>
    </div>
  );
}
