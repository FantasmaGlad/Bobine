"use client";

import { truncateLabel, type GraphLayout, type GraphSink, type GraphSource } from "@/lib/routingGraph";
import { type SectionProps } from "../common";
import { sinkIcon, sinkSub, sourceIcon, sourceLabel, sourceSub } from "./graphText";
import { type GraphInteraction } from "./useGraphInteraction";

type Node = GraphLayout["nodes"][number];
type T = SectionProps["t"];

function NodeFace({ node, icon, label, sub }: { node: Node; icon: string; label: string; sub: string }) {
  return (
    <>
      <rect className="rt-node-card" width={node.width} height={node.height} rx={14} />
      <rect className="rt-node-ring" width={node.width} height={node.height} rx={14} />
      <text className="material-symbols-outlined rt-node-icon" x={24} y={node.height / 2} textAnchor="middle" dominantBaseline="central">{icon}</text>
      <text className="rt-node-label" x={46} y={node.height / 2 - 7}>{truncateLabel(label, 28)}</text>
      <text className="rt-node-sub" x={46} y={node.height / 2 + 12}>{truncateLabel(sub, 32)}</text>
    </>
  );
}

interface SourceProps {
  source: GraphSource;
  node: Node;
  disabled: boolean;
  ui: GraphInteraction;
  t: T;
}

export function SourceNode({ source, node, disabled, ui, t }: SourceProps) {
  const label = sourceLabel(source, t);
  const sub = sourceSub(source, t);
  const { picked, drag } = ui;
  const className = `rt-node rt-node--source${source.playing ? " is-playing" : ""}${source.draggable ? " is-draggable" : ""}${picked === source.id ? " is-picked" : ""}${drag?.id === source.id && drag.moved ? " is-dragging" : ""}`;
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={`${label} — ${sub}`}
      aria-pressed={source.draggable ? picked === source.id : undefined}
      aria-disabled={source.draggable ? disabled : undefined}
      data-node={source.id}
      transform={`translate(${node.x} ${node.y})`}
      className={className}
      onPointerDown={(e) => ui.onPointerDown(e, source)}
      onClick={(event) => ui.onSourceClick(event, source)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ui.activate(source); } }}
    >
      <NodeFace node={node} icon={sourceIcon(source)} label={label} sub={sub} />
    </g>
  );
}

interface SinkProps {
  sink: GraphSink;
  node: Node;
  receiving: boolean;
  over: string | null;
  ui: GraphInteraction;
  t: T;
}

export function SinkNode({ sink, node, receiving, over, ui, t }: SinkProps) {
  const sub = sinkSub(sink, t);
  const { picked, assign } = ui;
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={`${sink.label} — ${sub}`}
      aria-disabled={sink.absent || undefined}
      data-node={sink.id}
      transform={`translate(${node.x} ${node.y})`}
      className={`rt-node rt-node--sink${sink.absent ? " is-absent" : ""}${receiving ? " is-target" : ""}${over === sink.id ? " is-over" : ""}`}
      onClick={() => { if (picked) assign(picked, sink.id); }}
      onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && picked) { e.preventDefault(); assign(picked, sink.id); } }}
    >
      <NodeFace node={node} icon={sinkIcon(sink)} label={sink.label} sub={sub} />
    </g>
  );
}
