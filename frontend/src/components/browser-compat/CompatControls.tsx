import Icon from "@/components/Icon";
import { type VideoProfilePreference } from "@/lib/clientCodecSupport";

type T = (key: string, params?: Record<string, string | number>) => string;

const PROFILE_KEYS = { auto: "browserCompat.profileAuto", web: "browserCompat.profileWeb", original: "browserCompat.profileOriginal" } as const;

export function ProfileChooser({ preference, onChange, t }: { preference: VideoProfilePreference; onChange: (value: VideoProfilePreference) => void; t: T }) {
  return (
    <div style={{ marginTop: 16 }}>
      <strong>{t("browserCompat.profileTitle")}</strong>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
        {(["auto", "web", "original"] as const).map((value) => (
          <button
            key={value}
            type="button"
            className={`btn btn-sm ${preference === value ? "btn-primary" : "btn-secondary"}`}
            aria-pressed={preference === value}
            onClick={() => onChange(value)}
          >
            {t(PROFILE_KEYS[value])}
          </button>
        ))}
      </div>
      <p className="settings-hint">{t("browserCompat.profileHint")}</p>
    </div>
  );
}

interface ActionsProps {
  running: boolean;
  text: string | null;
  copied: boolean;
  onTest: () => void;
  onCopy: () => void;
  t: T;
}

export function CompatActions({ running, text, copied, onTest, onCopy, t }: ActionsProps) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
      <button type="button" className="btn btn-secondary btn-sm" disabled={running} onClick={onTest}>
        {running ? t("browserCompat.testing") : t("browserCompat.testButton")}
      </button>
      <button type="button" className="btn btn-secondary btn-sm" onClick={onCopy}>
        <Icon name="content_copy" size={14} /> {copied ? t("browserCompat.reportCopied") : t("browserCompat.copyReport")}
      </button>
      {text && <span style={{ fontSize: "0.85rem" }}>{text}</span>}
    </div>
  );
}

export function CompatTips({ t }: { t: T }) {
  return (
    <details style={{ marginTop: 12 }}>
      <summary>{t("browserCompat.tipsTitle")}</summary>
      <ul className="settings-hint" style={{ paddingLeft: 18 }}>
        <li>{t("browserCompat.tipLinux")}</li>
        <li>{t("browserCompat.tipWindows")}</li>
        <li>{t("browserCompat.tipMac")}</li>
        <li>{t("browserCompat.tipAndroid")}</li>
      </ul>
    </details>
  );
}
