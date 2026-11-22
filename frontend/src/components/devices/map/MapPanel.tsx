"use client";

import Icon from "@/components/Icon";
import { linkStyle, nodeIcon, type PlacedNode, type Topology } from "@/lib/deviceMap";
import { type SectionProps } from "../shared/section";
import MediumLine from "./MediumLine";
import { panelRows } from "./mapText";

export type OpenTab = (tab: "audio" | "bluetooth", ref: string | null) => void;

interface PanelProps {
  node: PlacedNode;
  label: string;
  topology: Topology;
  t: SectionProps["t"];
  onClose: () => void;
  onOpen: OpenTab;
}

export default function MapPanel({ node, label, topology, t, onClose, onOpen }: PanelProps) {
  const link = topology.links.find((l) => l.to === node.id);
  const rows = panelRows(node, label, topology, t);
  const tab = node.tab;
  return (
    <aside className="dv-map-panel" role="dialog" aria-label={label}>
      <header>
        <span className="dv-icon"><Icon name={nodeIcon(node)} size={22} /></span>
        <span className="dv-text"><span className="dv-title">{label}</span><span className="dv-sub">{t(`devices.map.kinds.${node.kind}`)}</span></span>
        <button type="button" className="dv-icon-btn" onClick={onClose} aria-label={t("devices.audio.detail.close")}><Icon name="close" size={18} /></button>
      </header>
      {link && (
        <p className="dv-map-conn">
          <MediumLine medium={link.medium} style={linkStyle(link.medium)} />
          {t(`devices.map.medium.${link.medium}`)} · {t(`devices.map.state.${link.state}`)}
        </p>
      )}
      <dl className="dv-defs">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      {tab && (
        <button type="button" className="btn btn-primary" onClick={() => onOpen(tab, node.ref)}>
          <Icon name="open_in_new" size={16} /> {t(`devices.map.open.${tab}`)}
        </button>
      )}
    </aside>
  );
}
