"use client";

import React, { useMemo } from "react";
import Icon from "@/components/Icon";
import { layoutRoutingGraph, sinkAt, type Assignment, type GraphLayout, type GraphSource, type RoutingGraphModel } from "@/lib/routingGraph";
import type { SectionProps } from "./shared/section";
import { SinkNode, SourceNode } from "./routing/GraphNodes";
import { sourceLabel } from "./routing/graphText";
import { useGraphInteraction, type GraphInteraction } from "./routing/useGraphInteraction";

interface Props {
  model: RoutingGraphModel;
  t: SectionProps["t"];
  disabled: boolean;
  onAssign: (assignment: Assignment) => void;
}

function GraphHint({ pickedSource, ui, t }: { pickedSource: GraphSource | null | undefined; ui: GraphInteraction; t: SectionProps["t"] }) {
  return (
    <p className="rt-graph-hint" aria-live="polite">
      <Icon name={pickedSource ? "touch_app" : "info"} size={16} />
      {pickedSource
        ? t("devices.routing.graph.hintPicked", { name: sourceLabel(pickedSource, t) })
        : t("devices.routing.graph.hintIdle")}
      {pickedSource && (
        <button type="button" className="dv-link-btn" onClick={() => ui.setPicked(null)}>{t("devices.routing.graph.cancel")}</button>
      )}
    </p>
  );
}

function GraphEdges({ layout, ui }: { layout: GraphLayout; ui: GraphInteraction }) {
  const { drag } = ui;
  const dragFrom = drag?.moved ? layout.nodes.find((n) => n.id === drag.id) : null;
  return (
    <>
      {layout.edges.map((edge) => (
        <path
          key={edge.id}
          d={edge.d}
          fill="none"
          className={`rt-edge rt-edge--${edge.kind}${edge.playing ? " is-playing" : ""}${edge.absent ? " is-absent" : ""}`}
        />
      ))}
      {dragFrom && drag && (
        <path
          className="rt-edge rt-edge--ghost"
          fill="none"
          d={`M${dragFrom.x + dragFrom.width} ${dragFrom.y + dragFrom.height / 2} L${drag.x} ${drag.y}`}
        />
      )}
    </>
  );
}

export default function RoutingGraph({ model, t, disabled, onAssign }: Props) {
  const layout: GraphLayout = useMemo(() => layoutRoutingGraph(model), [model]);
  const ui = useGraphInteraction({ model, layout, disabled, onAssign });
  const { svgRef, drag, picked, setPicked, onPointerMove, onPointerUp } = ui;
  const nodeOf = (id: string) => layout.nodes.find((n) => n.id === id);
  const over = drag?.moved ? sinkAt(layout, { x: drag.x, y: drag.y }) : null;
  const pickedSource = picked ? model.sources.find((s) => s.id === picked) : null;

  return (
    <div className="rt-graph-wrap">
      <div className="rt-graph-frame" onKeyDown={(e) => { if (e.key === "Escape") setPicked(null); }}>
        <svg
          ref={svgRef}
          className="rt-graph"
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          width={layout.width}
          height={layout.height}
          role="group"
          aria-label={t("devices.routing.graph.title")}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <GraphEdges layout={layout} ui={ui} />
          {model.sources.map((source) => {
            const node = nodeOf(source.id);
            return node ? <SourceNode key={source.id} source={source} node={node} disabled={disabled} ui={ui} t={t} /> : null;
          })}
          {model.sinks.map((sink) => {
            const node = nodeOf(sink.id);
            return node ? <SinkNode key={sink.id} sink={sink} node={node} receiving={!!pickedSource && !sink.absent} over={over} ui={ui} t={t} /> : null;
          })}
        </svg>
      </div>
      <GraphHint pickedSource={pickedSource} ui={ui} t={t} />
    </div>
  );
}
