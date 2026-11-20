import { type Capabilities } from "./capabilities";

type T = (key: string, params?: Record<string, string | number>) => string;

const ROW_STYLE = { display: "flex", justifyContent: "space-between", gap: 12, fontSize: "0.88rem" } as const;
const LIST_STYLE = { listStyle: "none", padding: 0, margin: "6px 0 0" } as const;

function Mark({ ok, t }: { ok: boolean; t: T }) {
  return (
    <span style={{ color: ok ? "var(--accent-success-text)" : "var(--text-muted)", fontWeight: 600 }}>
      {ok ? t("browserCompat.yes") : t("browserCompat.no")}
    </span>
  );
}

export default function CompatLists({ caps, t }: { caps: Capabilities; t: T }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
      <div>
        <strong>{t("browserCompat.codecsTitle")}</strong>
        <ul style={LIST_STYLE}>
          {caps.codecs.map((c) => (
            <li key={c.label} style={ROW_STYLE}>
              <span>{c.label}</span>
              <Mark ok={c.support !== ""} t={t} />
            </li>
          ))}
        </ul>
      </div>
      <div>
        <strong>{t("browserCompat.apisTitle")}</strong>
        <ul style={LIST_STYLE}>
          <li style={ROW_STYLE}>
            <span>{t("browserCompat.secureContext")}</span>
            <Mark ok={caps.secure} t={t} />
          </li>
          {caps.features.map((f) => (
            <li key={f.label} style={ROW_STYLE}>
              <span>{f.label}</span>
              <Mark ok={f.supported} t={t} />
            </li>
          ))}
        </ul>
        {!caps.secure && <p className="settings-hint">{t("browserCompat.secureContextHint")}</p>}
      </div>
    </div>
  );
}
