import { useRef, useState } from "react";
import { assignmentFor, sinkAt, type Assignment, type GraphLayout, type GraphSource, type RoutingGraphModel } from "@/lib/routingGraph";

const DRAG_THRESHOLD = 6;

type Drag = { id: string; x: number; y: number; moved: boolean };

interface Options {
  model: RoutingGraphModel;
  layout: GraphLayout;
  disabled: boolean;
  onAssign: (assignment: Assignment) => void;
}

function graphPoint(svg: SVGSVGElement | null, event: React.PointerEvent): { x: number; y: number } {
  const matrix = svg?.getScreenCTM();
  if (!svg || !matrix) return { x: 0, y: 0 };
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const local = point.matrixTransform(matrix.inverse());
  return { x: local.x, y: local.y };
}

function usePick({ model, disabled, onAssign }: Options, svgRef: React.RefObject<SVGSVGElement | null>) {
  const [picked, setPicked] = useState<string | null>(null);
  const assign = (sourceId: string, sinkId: string) => {
    const assignment = assignmentFor(model, sourceId, sinkId);
    setPicked(null);
    if (assignment && !disabled) onAssign(assignment);
  };
  const activate = (source: GraphSource) => {
    if (!source.draggable || disabled) return;
    setPicked((current) => (current === source.id ? null : source.id));
    requestAnimationFrame(() => svgRef.current?.querySelector<SVGGElement>(".rt-node--sink")?.focus());
  };
  return { picked, setPicked, assign, activate };
}

export function useGraphInteraction(options: Options) {
  const { model, layout, disabled } = options;
  const svgRef = useRef<SVGSVGElement>(null);
  const pick = usePick(options, svgRef);
  const [drag, setDrag] = useState<Drag | null>(null);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  const suppressClickUntil = useRef(0);

  const onPointerDown = (event: React.PointerEvent, source: GraphSource) => {
    if (event.button !== 0 || !source.draggable || disabled) return;
    startRef.current = { x: event.clientX, y: event.clientY };
    svgRef.current?.setPointerCapture(event.pointerId);
    const p = graphPoint(svgRef.current, event);
    setDrag({ id: source.id, x: p.x, y: p.y, moved: false });
  };
  const onPointerMove = (event: React.PointerEvent) => {
    if (!drag || !startRef.current) return;
    const moved = drag.moved || Math.hypot(event.clientX - startRef.current.x, event.clientY - startRef.current.y) > DRAG_THRESHOLD;
    const p = graphPoint(svgRef.current, event);
    setDrag({ ...drag, x: p.x, y: p.y, moved });
  };
  const onPointerUp = (event: React.PointerEvent) => {
    if (!drag) return;
    const current = drag;
    setDrag(null);
    startRef.current = null;
    if (svgRef.current?.hasPointerCapture(event.pointerId)) svgRef.current.releasePointerCapture(event.pointerId);
    suppressClickUntil.current = event.timeStamp + 400;
    if (!current.moved) {
      const source = model.sources.find((s) => s.id === current.id);
      if (source) pick.activate(source);
      return;
    }
    const target = sinkAt(layout, graphPoint(svgRef.current, event));
    if (target) pick.assign(current.id, target);
  };
  const onSourceClick = (event: React.MouseEvent, source: GraphSource) => {
    if (event.timeStamp >= suppressClickUntil.current) pick.activate(source);
  };

  return { svgRef, drag, ...pick, onPointerDown, onPointerMove, onPointerUp, onSourceClick };
}

export type GraphInteraction = ReturnType<typeof useGraphInteraction>;
