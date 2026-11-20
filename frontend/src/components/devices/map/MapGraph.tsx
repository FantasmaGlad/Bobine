"use client";

import { curvePath, linkStyle, neighborhood, nodeIcon, type MapLayout, type PlacedNode } from "@/lib/deviceMap";
import { type SectionProps } from "../shared/section";
import { nodeLabel, truncate } from "./mapText";

type Near = ReturnType<typeof neighborhood> | null;

interface NodeProps {
  node: PlacedNode;
  near: Near;
  selected: string | null;
  setSelected: (id: string) => void;
  setHover: React.Dispatch<React.SetStateAction<string | null>>;
  t: SectionProps["t"];
}

function MapNode({ node, near, selected, setSelected, setHover, t }: NodeProps) {
  const dim = near && !near.nodes.has(node.id);
  const label = nodeLabel(node, t);
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={`${label} — ${node.sub}`}
      className={`dv-node dv-node--${node.kind} ${node.state} ${selected === node.id ? "selected" : ""} ${dim ? "dim" : ""}`}
      transform={`translate(${node.x} ${node.y})`}
      onPointerEnter={() => setHover(node.id)}
      onPointerLeave={() => setHover((h) => (h === node.id ? null : h))}
      onFocus={() => setHover(node.id)}
      onBlur={() => setHover((h) => (h === node.id ? null : h))}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => { e.stopPropagation(); setSelected(node.id); }}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(node.id); } }}
    >
      <circle r={node.r + 7} className="dv-node-halo" />
      <circle r={node.r} className="dv-node-disc" />
      <text className="material-symbols-outlined dv-node-icon" textAnchor="middle" dominantBaseline="central" style={{ fontSize: node.r * 0.95 }}>{nodeIcon(node)}</text>
      <text className="dv-node-label" textAnchor="middle" y={node.r + 17}>{truncate(label)}</text>
    </g>
  );
}

function MapLinks({ layout, near }: { layout: MapLayout; near: Near }) {
  return (
    <>
      {layout.links.map((link) => {
        const style = linkStyle(link.medium);
        const dim = near && !near.links.has(link.id);
        return (
          <path
            key={link.id}
            d={curvePath(link.a, link.b, 0.06)}
            className={`dv-link dv-link--${link.medium} ${link.state} ${dim ? "dim" : ""} ${near && !dim ? "hot" : ""}`}
            fill="none"
            strokeDasharray={style.dash || undefined}
            strokeLinecap={style.cap}
            strokeWidth={style.width}
          />
        );
      })}
    </>
  );
}

export default function MapGraph({ layout, ...nodeProps }: { layout: MapLayout } & Omit<NodeProps, "node">) {
  return (
    <>
      {layout.rings.map((radius) => <circle key={radius} r={radius} className="dv-ring" />)}
      <MapLinks layout={layout} near={nodeProps.near} />
      {layout.nodes.map((node) => <MapNode key={node.id} node={node} {...nodeProps} />)}
    </>
  );
}
