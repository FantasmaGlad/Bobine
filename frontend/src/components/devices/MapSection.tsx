"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Icon from "@/components/Icon";
import {
  curvePath, fitView, layoutOrbits, linkStyle, neighborhood, nodeIcon, zoomAt,
  type PlacedNode, type Topology,
} from "@/lib/deviceMap";
import { useDevicesResource, type SectionProps } from "./common";

interface Props extends Pick<SectionProps, "refreshKey" | "t"> {
  /** Raccourci : ouvre l'onglet de l'appareil et le met en évidence. */
  onOpen: (tab: "audio" | "bluetooth" | "wifi", ref: string | null) => void;
}

type View = { scale: number; tx: number; ty: number };

const truncate = (text: string, max = 18) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

/** Carte « système solaire » : la machine au centre, ses connexions autour. SVG léger, déplacement et zoom. */
export default function MapSection({ refreshKey, t, onOpen }: Props) {
  const { data, error, loading, reload } = useDevicesResource<Topology>("/topology", refreshKey);
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState<View>({ scale: 1, tx: 0, ty: 0 });
  const [size, setSize] = useState({ width: 800, height: 520 });
  const frameRef = useRef<HTMLDivElement>(null);
  const interacted = useRef(false);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<number | null>(null);
  const dragged = useRef(false);

  // Relecture périodique (les évènements `devices_changed` ne couvrent pas les écrans Bobine connectés).
  useEffect(() => {
    const timer = setInterval(() => { void reload(); }, 15000);
    return () => clearInterval(timer);
  }, [reload]);

  const layout = useMemo(() => (data ? layoutOrbits(data) : null), [data]);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => setSize({ width: frame.clientWidth, height: frame.clientHeight }));
    observer.observe(frame);
    setSize({ width: frame.clientWidth, height: frame.clientHeight });
    return () => observer.disconnect();
  }, [layout !== null]); // eslint-disable-line react-hooks/exhaustive-deps -- le cadre n'existe qu'une fois la carte chargée

  const recenter = useCallback(() => {
    interacted.current = false;
    if (layout) setView(fitView(layout.bounds, size));
  }, [layout, size]);

  // Cadrage automatique (tout tient dans le cadre) tant que l'utilisateur n'a pas déplacé ou zoomé la carte.
  useEffect(() => {
    if (layout && !interacted.current && size.width > 50) setView(fitView(layout.bounds, size));
  }, [layout, size]);

  // Molette : zoom autour du curseur (écouteur non passif pour bloquer le défilement de la page).
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      interacted.current = true;
      const rect = frame.getBoundingClientRect();
      const point = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      setView((v) => zoomAt(v, point, Math.exp(-event.deltaY * 0.0015)));
    };
    frame.addEventListener("wheel", onWheel, { passive: false });
    return () => frame.removeEventListener("wheel", onWheel);
  }, [layout !== null]); // eslint-disable-line react-hooks/exhaustive-deps

  const onPointerDown = (event: React.PointerEvent) => {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    dragged.current = false;
    (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinch.current = Math.hypot(a.x - b.x, a.y - b.y);
    }
  };
  const onPointerMove = (event: React.PointerEvent) => {
    const previous = pointers.current.get(event.pointerId);
    if (!previous) return;
    const next = { x: event.clientX, y: event.clientY };
    pointers.current.set(event.pointerId, next);
    if (pointers.current.size === 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      const rect = frameRef.current?.getBoundingClientRect();
      if (rect && distance > 0) {
        const mid = { x: (a.x + b.x) / 2 - rect.left, y: (a.y + b.y) / 2 - rect.top };
        setView((v) => zoomAt(v, mid, distance / (pinch.current ?? distance)));
      }
      pinch.current = distance;
      dragged.current = true;
      interacted.current = true;
      return;
    }
    const dx = next.x - previous.x;
    const dy = next.y - previous.y;
    if (dx !== 0 || dy !== 0) {
      if (Math.abs(dx) + Math.abs(dy) > 2) { dragged.current = true; interacted.current = true; }
      setView((v) => ({ ...v, tx: v.tx + dx, ty: v.ty + dy }));
    }
  };
  const onPointerUp = (event: React.PointerEvent) => {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "+" || event.key === "=" || event.key === "-") interacted.current = true;
    if (event.key === "Escape") setSelected(null);
    else if (event.key === "+" || event.key === "=") setView((v) => zoomAt(v, { x: size.width / 2, y: size.height / 2 }, 1.2));
    else if (event.key === "-") setView((v) => zoomAt(v, { x: size.width / 2, y: size.height / 2 }, 1 / 1.2));
    else if (event.key === "0") recenter();
  };

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error || !data || !layout) return <div className="rl-center-note">{t("devices.errors.generic")}</div>;

  const focusId = hover ?? selected;
  const near = focusId ? neighborhood(data.links, focusId) : null;
  const selectedNode = layout.nodes.find((n) => n.id === selected) ?? null;
  const labelOf = (n: PlacedNode) => {
    if (n.kind !== "screen" && n.kind !== "remote") return n.label;
    const page = String(n.meta.page ?? "viewer");
    const key = `devices.map.pages.${page}`;
    const name = t(key) === key ? page : t(key);
    const count = Number(n.meta.count ?? 1);
    return count > 1 ? `${name} ×${count}` : name;
  };

  return (
    <div className="dv-map-wrap">
      <div className="dv-map-legend" aria-label={t("devices.map.legend")}>
        {(["wifi", "bluetooth", "wired"] as const).map((medium) => {
          const style = linkStyle(medium);
          return (
            <span key={medium} className="dv-legend-item">
              <svg width="38" height="10" aria-hidden="true"><line x1="2" y1="5" x2="36" y2="5" className={`dv-link dv-link--${medium} active`} strokeDasharray={style.dash || undefined} strokeLinecap={style.cap} strokeWidth={style.width} /></svg>
              {t(`devices.map.medium.${medium}`)}
            </span>
          );
        })}
        <span className="dv-legend-item dv-legend-count">{t("devices.map.counts", { audio: data.counts.audio, bluetooth: data.counts.bluetooth, screens: data.counts.screens })}</span>
      </div>

      <div className="dv-map-frame" ref={frameRef} tabIndex={0} onKeyDown={onKeyDown} aria-label={t("devices.map.title")}>
        <svg
          className="dv-map"
          width={size.width}
          height={size.height}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onClick={() => { if (!dragged.current) setSelected(null); }}
        >
          <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
            {layout.rings.map((radius) => <circle key={radius} r={radius} className="dv-ring" />)}
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
            {layout.nodes.map((node) => {
              const dim = near && !near.nodes.has(node.id);
              return (
                <g
                  key={node.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${labelOf(node)} — ${node.sub}`}
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
                  <text className="dv-node-label" textAnchor="middle" y={node.r + 17}>{truncate(labelOf(node))}</text>
                </g>
              );
            })}
          </g>
        </svg>

        <div className="dv-map-controls">
          <button type="button" className="dv-map-btn" aria-label={t("devices.map.zoomIn")} onClick={() => { interacted.current = true; setView((v) => zoomAt(v, { x: size.width / 2, y: size.height / 2 }, 1.25)); }}><Icon name="add" size={18} /></button>
          <button type="button" className="dv-map-btn" aria-label={t("devices.map.zoomOut")} onClick={() => { interacted.current = true; setView((v) => zoomAt(v, { x: size.width / 2, y: size.height / 2 }, 0.8)); }}><Icon name="remove" size={18} /></button>
          <button type="button" className="dv-map-btn" aria-label={t("devices.map.recenter")} onClick={recenter}><Icon name="center_focus_strong" size={18} /></button>
        </div>

        {selectedNode && <MapPanel node={selectedNode} label={labelOf(selectedNode)} topology={data} t={t} onClose={() => setSelected(null)} onOpen={onOpen} />}
        {data.nodes.length <= 1 && <p className="dv-map-empty">{t("devices.map.empty")}</p>}
      </div>
    </div>
  );
}

function MapPanel({ node, label, topology, t, onClose, onOpen }: {
  node: PlacedNode; label: string; topology: Topology; t: SectionProps["t"]; onClose: () => void;
  onOpen: Props["onOpen"];
}) {
  const link = topology.links.find((l) => l.to === node.id);
  const m = node.meta;
  const rows: [string, string][] = [];
  const push = (key: string, value: unknown) => { if (value !== null && value !== undefined && value !== "") rows.push([t(`devices.map.fields.${key}`), String(value)]); };
  switch (node.kind) {
    case "machine":
      push("platform", node.sub);
      push("audio", topology.counts.audio);
      push("bluetooth", topology.counts.bluetooth);
      push("screens", topology.counts.screens);
      break;
    case "wifi":
      push("network", node.label); push("signal", m.signal !== undefined ? `${m.signal} %` : null); push("band", m.band); push("security", m.security || t("devices.wifi.open")); push("ip", m.ip);
      break;
    case "ethernet":
      push("interface", m.interface); push("ip", m.ip); push("speed", m.speed ? `${m.speed} Mb/s` : null);
      break;
    case "bluetooth":
      push("address", m.address); push("state", m.connected ? t("devices.bluetooth.connected") : t("devices.map.paired"));
      push("profiles", Array.isArray(m.profiles) ? (m.profiles as string[]).join(", ") : null); push("battery", m.battery !== null && m.battery !== undefined ? `${m.battery} %` : null);
      push("audioOutput", m.audio_id ? t(m.audio_default ? "devices.map.audioDefault" : "devices.map.audioAvailable") : null);
      break;
    case "audio":
      push("type", t(`devices.audio.kind.${m.device_kind}`)); push("state", m.default ? t("devices.audio.default") : t("devices.map.idle"));
      push("volume", typeof m.volume === "number" ? `${Math.round(m.volume * 100)} %` : null);
      break;
    default:
      push("page", label); push("channel", t(`devices.map.channels.${m.channel}`)); push("role", t(`devices.map.roles.${m.role}`));
      push("address", m.ip || t("devices.map.localScreen")); push("link", t(`devices.map.medium.${m.medium}`)); push("count", Number(m.count ?? 1) > 1 ? m.count : null);
  }
  return (
    <aside className="dv-map-panel" role="dialog" aria-label={label}>
      <header>
        <span className="dv-icon"><Icon name={nodeIcon(node)} size={22} /></span>
        <span className="dv-text"><span className="dv-title">{label}</span><span className="dv-sub">{t(`devices.map.kinds.${node.kind}`)}</span></span>
        <button type="button" className="dv-icon-btn" onClick={onClose} aria-label={t("devices.audio.detail.close")}><Icon name="close" size={18} /></button>
      </header>
      {link && (
        <p className="dv-map-conn">
          <svg width="38" height="10" aria-hidden="true"><line x1="2" y1="5" x2="36" y2="5" className={`dv-link dv-link--${link.medium} active`} strokeDasharray={linkStyle(link.medium).dash || undefined} strokeLinecap={linkStyle(link.medium).cap} strokeWidth={linkStyle(link.medium).width} /></svg>
          {t(`devices.map.medium.${link.medium}`)} · {t(`devices.map.state.${link.state}`)}
        </p>
      )}
      <dl className="dv-defs">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      {node.tab && (
        <button type="button" className="btn btn-primary" onClick={() => onOpen(node.tab as "audio" | "bluetooth" | "wifi", node.ref)}>
          <Icon name="open_in_new" size={16} /> {t(`devices.map.open.${node.tab}`)}
        </button>
      )}
    </aside>
  );
}
