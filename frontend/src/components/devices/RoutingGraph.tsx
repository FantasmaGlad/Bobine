"use client";

import React, { useMemo, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { audioKindIcon } from "@/lib/devicesApi";
import {
  assignmentFor, layoutRoutingGraph, sinkAt, truncateLabel,
  type Assignment, type GraphLayout, type GraphSink, type GraphSource, type RoutingGraphModel,
} from "@/lib/routingGraph";
import type { SectionProps } from "./common";

interface Props {
  model: RoutingGraphModel;
  t: SectionProps["t"];
  /** Désactivé pendant un enregistrement ou quand la plateforme ne permet pas de router. */
  disabled: boolean;
  onAssign: (assignment: Assignment) => void;
}

/** Au-delà de ce déplacement (px écran), un appui devient un glisser (en deçà : un simple clic de sélection). */
const DRAG_THRESHOLD = 6;

function sourceIcon(source: GraphSource): string {
  if (source.kind === "radio") return "radio";
  return source.kind === "announcements" ? "campaign" : "movie";
}

function sinkIcon(sink: GraphSink): string {
  return sink.kind === "default" ? "volume_up" : audioKindIcon(sink.kind);
}

/**
 * Graphe de routage : sources à gauche, sorties à droite. Glisser une radio vers une sortie la re-route ; à la
 * télécommande ou au clavier : Entrée sur la radio, puis Entrée sur la sortie (Échap annule). Tous les nœuds sont
 * focalisables (navigation spatiale), l'état en direct est porté par la couleur ET par le texte.
 */
export default function RoutingGraph({ model, t, disabled, onAssign }: Props) {
  const layout: GraphLayout = useMemo(() => layoutRoutingGraph(model), [model]);
  const svgRef = useRef<SVGSVGElement>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ id: string; x: number; y: number; moved: boolean } | null>(null);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  // Après un appui à la souris ou au doigt, le navigateur peut émettre un « click » en plus (selon la capture du pointeur).
  const suppressClickUntil = useRef(0);

  const nodeOf = (id: string) => layout.nodes.find((n) => n.id === id);
  const sourceOf = (id: string) => model.sources.find((s) => s.id === id);
  const sourceLabel = (s: GraphSource) => (s.channel ? t(`devices.map.channels.${s.channel}`) : t(`devices.routing.graph.${s.kind}`));
  const sourceSub = (s: GraphSource) => {
    if (s.kind === "radio") return s.playing ? t("devices.routing.playing") : t("devices.routing.stopped");
    return s.kind === "announcements" ? t("devices.routing.graph.announcementsSub") : t("devices.routing.graph.videoSub");
  };
  const sinkSub = (s: GraphSink) => {
    if (s.absent) return t("devices.routing.graph.absent");
    if (s.kind === "default") return t("devices.routing.graph.defaultSub");
    return `${t(`devices.audio.kind.${s.kind}`)}${s.isDefault ? ` · ${t("devices.audio.default")}` : ""}`;
  };

  const toGraphPoint = (event: React.PointerEvent): { x: number; y: number } => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return { x: 0, y: 0 };
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    return { x: local.x, y: local.y };
  };

  const assign = (sourceId: string, sinkId: string) => {
    const assignment = assignmentFor(model, sourceId, sinkId);
    setPicked(null);
    if (assignment && !disabled) onAssign(assignment);
  };

  const onSourceActivate = (source: GraphSource) => {
    if (!source.draggable || disabled) return;
    setPicked((current) => (current === source.id ? null : source.id));
    // Le focus passe aux sorties : un second Entrée (ou un clic) valide.
    requestAnimationFrame(() => svgRef.current?.querySelector<SVGGElement>(".rt-node--sink")?.focus());
  };

  const onPointerDown = (event: React.PointerEvent, source: GraphSource) => {
    if (event.button !== 0 || !source.draggable || disabled) return;
    startRef.current = { x: event.clientX, y: event.clientY };
    svgRef.current?.setPointerCapture(event.pointerId);
    const p = toGraphPoint(event);
    setDrag({ id: source.id, x: p.x, y: p.y, moved: false });
  };
  const onPointerMove = (event: React.PointerEvent) => {
    if (!drag || !startRef.current) return;
    const moved = drag.moved || Math.hypot(event.clientX - startRef.current.x, event.clientY - startRef.current.y) > DRAG_THRESHOLD;
    const p = toGraphPoint(event);
    setDrag({ ...drag, x: p.x, y: p.y, moved });
  };
  const onPointerUp = (event: React.PointerEvent) => {
    if (!drag) return;
    const current = drag;
    setDrag(null);
    startRef.current = null;
    if (svgRef.current?.hasPointerCapture(event.pointerId)) svgRef.current.releasePointerCapture(event.pointerId);
    suppressClickUntil.current = performance.now() + 400;
    if (!current.moved) {
      const source = sourceOf(current.id);
      if (source) onSourceActivate(source); // simple appui : sélection (puis clic sur une sortie)
      return;
    }
    const target = sinkAt(layout, toGraphPoint(event));
    if (target) assign(current.id, target);
  };

  const dragFrom = drag?.moved ? nodeOf(drag.id) : null;
  const over = drag?.moved ? sinkAt(layout, { x: drag.x, y: drag.y }) : null;
  const pickedSource = picked ? sourceOf(picked) : null;

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
          {model.sources.map((source) => {
            const node = nodeOf(source.id);
            if (!node) return null;
            const label = sourceLabel(source);
            return (
              <g
                key={source.id}
                role="button"
                tabIndex={0}
                aria-label={`${label} — ${sourceSub(source)}`}
                aria-pressed={source.draggable ? picked === source.id : undefined}
                aria-disabled={source.draggable ? disabled : undefined}
                data-node={source.id}
                transform={`translate(${node.x} ${node.y})`}
                className={`rt-node rt-node--source${source.playing ? " is-playing" : ""}${source.draggable ? " is-draggable" : ""}${picked === source.id ? " is-picked" : ""}${drag?.id === source.id && drag.moved ? " is-dragging" : ""}`}
                onPointerDown={(e) => onPointerDown(e, source)}
                onClick={() => { if (performance.now() >= suppressClickUntil.current) onSourceActivate(source); }}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSourceActivate(source); } }}
              >
                <rect className="rt-node-card" width={node.width} height={node.height} rx={14} />
                <rect className="rt-node-ring" width={node.width} height={node.height} rx={14} />
                <text className="material-symbols-outlined rt-node-icon" x={24} y={node.height / 2} textAnchor="middle" dominantBaseline="central">{sourceIcon(source)}</text>
                <text className="rt-node-label" x={46} y={node.height / 2 - 7}>{truncateLabel(label, 28)}</text>
                <text className="rt-node-sub" x={46} y={node.height / 2 + 12}>{truncateLabel(sourceSub(source), 32)}</text>
              </g>
            );
          })}
          {model.sinks.map((sink) => {
            const node = nodeOf(sink.id);
            if (!node) return null;
            const receiving = !!pickedSource && !sink.absent;
            return (
              <g
                key={sink.id}
                role="button"
                tabIndex={0}
                aria-label={`${sink.label} — ${sinkSub(sink)}`}
                aria-disabled={sink.absent || undefined}
                data-node={sink.id}
                transform={`translate(${node.x} ${node.y})`}
                className={`rt-node rt-node--sink${sink.absent ? " is-absent" : ""}${receiving ? " is-target" : ""}${over === sink.id ? " is-over" : ""}`}
                onClick={() => { if (picked) assign(picked, sink.id); }}
                onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && picked) { e.preventDefault(); assign(picked, sink.id); } }}
              >
                <rect className="rt-node-card" width={node.width} height={node.height} rx={14} />
                <rect className="rt-node-ring" width={node.width} height={node.height} rx={14} />
                <text className="material-symbols-outlined rt-node-icon" x={24} y={node.height / 2} textAnchor="middle" dominantBaseline="central">{sinkIcon(sink)}</text>
                <text className="rt-node-label" x={46} y={node.height / 2 - 7}>{truncateLabel(sink.label, 28)}</text>
                <text className="rt-node-sub" x={46} y={node.height / 2 + 12}>{truncateLabel(sinkSub(sink), 32)}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="rt-graph-hint" aria-live="polite">
        <Icon name={pickedSource ? "touch_app" : "info"} size={16} />
        {pickedSource
          ? t("devices.routing.graph.hintPicked", { name: sourceLabel(pickedSource) })
          : t("devices.routing.graph.hintIdle")}
        {pickedSource && (
          <button type="button" className="dv-link-btn" onClick={() => setPicked(null)}>{t("devices.routing.graph.cancel")}</button>
        )}
      </p>
    </div>
  );
}
