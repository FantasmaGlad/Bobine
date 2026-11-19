import { type linkStyle } from "@/lib/deviceMap";

export default function MediumLine({ medium, style }: { medium: string; style: ReturnType<typeof linkStyle> }) {
  return (
    <svg width="38" height="10" aria-hidden="true"><line x1="2" y1="5" x2="36" y2="5" className={`dv-link dv-link--${medium} active`} strokeDasharray={style.dash || undefined} strokeLinecap={style.cap} strokeWidth={style.width} /></svg>
  );
}
