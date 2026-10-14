"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import {
  VideoProfilePreference,
  getAcceptedCodecs,
  getVideoProfilePreference,
  setVideoProfilePreference,
} from "@/lib/clientCodecSupport";

function getApiUrl(path: string): string {
  if (typeof window !== "undefined" && window.location.port === "3000") return `http://localhost:8001/api${path}`;
  return `/api${path}`;
}

const CODEC_ROWS: ReadonlyArray<readonly [string, string, string]> = [
  ["H.264 (AVC)", "h264", 'video/mp4; codecs="avc1.640028"'],
  ["H.264 High 10", "hi10", 'video/mp4; codecs="avc1.6E0028"'],
  ["H.265 (HEVC)", "hevc", 'video/mp4; codecs="hvc1.1.6.L93.B0"'],
  ["VP9", "vp9", 'video/mp4; codecs="vp09.00.10.08"'],
  ["AV1", "av1", 'video/mp4; codecs="av01.0.08M.08"'],
  ["AAC", "aac", 'audio/mp4; codecs="mp4a.40.2"'],
  ["MP3", "mp3", "audio/mpeg"],
  ["Opus", "opus", 'audio/webm; codecs="opus"'],
  ["FLAC", "flac", "audio/flac"],
];

interface FeatureRow {
  label: string;
  supported: boolean;
}

function detectFeatures(): FeatureRow[] {
  const video = document.createElement("video");
  return [
    { label: "WebSocket", supported: "WebSocket" in window },
    { label: "Web Audio (AudioContext)", supported: "AudioContext" in window || "webkitAudioContext" in window },
    { label: "Screen Wake Lock", supported: "wakeLock" in navigator },
    { label: "Gamepad API", supported: "getGamepads" in navigator },
    { label: "Media Session", supported: "mediaSession" in navigator },
    { label: "MediaCapabilities", supported: "mediaCapabilities" in navigator },
    { label: "requestVideoFrameCallback", supported: "requestVideoFrameCallback" in video },
    { label: "Fullscreen API", supported: !!document.documentElement.requestFullscreen },
    { label: "Dossier glissé (webkitdirectory)", supported: "webkitdirectory" in document.createElement("input") },
  ];
}

interface Capabilities {
  secure: boolean;
  codecs: Array<{ label: string; support: string }>;
  features: FeatureRow[];
  accept: string;
  cores: number | null;
}

function collect(): Capabilities {
  const video = document.createElement("video");
  const audio = document.createElement("audio");
  return {
    secure: window.isSecureContext,
    codecs: CODEC_ROWS.map(([label, , type]) => ({
      label,
      support: (type.startsWith("audio") ? audio : video).canPlayType(type) || "",
    })),
    features: detectFeatures(),
    accept: getAcceptedCodecs(),
    cores: navigator.hardwareConcurrency || null,
  };
}

/**
 * Réglages → Compatibilité navigateur (lot F5 du plan Firefox) : diagnostic
 * local de CE navigateur, choix de la version vidéo utilisée, mesure de lecture
 * réelle et rapport copiable. Aucune donnée n'est envoyée nulle part.
 */
export default function BrowserCompatibility() {
  const { t } = useAppSettings();
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [preference, setPreference] = useState<VideoProfilePreference>("auto");
  const [autoGenerate, setAutoGenerate] = useState(false);
  const [testState, setTestState] = useState<{ running: boolean; text: string | null }>({ running: false, text: null });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- détection de fonctionnalités : possible seulement côté navigateur
    setCaps(collect());
    setPreference(getVideoProfilePreference());
    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setAutoGenerate(data?.auto_web_rendition === "true"))
      .catch(() => {});
  }, []);

  const changePreference = (value: VideoProfilePreference) => {
    setVideoProfilePreference(value);
    setPreference(value);
  };

  const toggleAutoGenerate = async (checked: boolean) => {
    setAutoGenerate(checked);
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_web_rendition: checked ? "true" : "false" }),
      });
      if (!res.ok) setAutoGenerate(!checked);
    } catch {
      setAutoGenerate(!checked);
    }
  };

  const runPlaybackTest = async () => {
    setTestState({ running: true, text: null });
    let element: HTMLVideoElement | null = null;
    try {
      const res = await fetch(getApiUrl("/videos?limit=1&sort_by=imported_at"), { cache: "no-store" });
      const videos = res.ok ? await res.json() : [];
      if (!videos.length) {
        setTestState({ running: false, text: t("browserCompat.testNoVideo") });
        return;
      }
      const { videoStreamUrl } = await import("@/lib/clientCodecSupport");
      element = document.createElement("video");
      element.muted = true;
      element.playsInline = true;
      element.preload = "auto";
      element.style.cssText = "position:fixed;width:1px;height:1px;opacity:0;pointer-events:none";
      document.body.appendChild(element);
      element.src = videoStreamUrl(getApiUrl, videos[0].id);
      await element.play();
      await new Promise((resolve) => setTimeout(resolve, 5000));
      const quality = element.getVideoPlaybackQuality?.();
      setTestState({
        running: false,
        text: t("browserCompat.testResult", {
          dropped: quality?.droppedVideoFrames ?? 0,
          total: quality?.totalVideoFrames ?? 0,
          video: `${element.videoWidth}x${element.videoHeight}`,
        }),
      });
    } catch (err) {
      setTestState({ running: false, text: t("browserCompat.testError", { reason: (err as Error).name || "erreur" }) });
    } finally {
      element?.remove();
    }
  };

  const copyReport = async () => {
    if (!caps) return;
    const report = JSON.stringify(
      {
        secureContext: caps.secure,
        hardwareConcurrency: caps.cores,
        accept: caps.accept,
        codecs: Object.fromEntries(caps.codecs.map((c) => [c.label, c.support || "non"])),
        features: Object.fromEntries(caps.features.map((f) => [f.label, f.supported])),
        playback: testState.text,
        userAgent: navigator.userAgent, // utile au support ; jamais utilisé pour adapter le comportement
      },
      null,
      2,
    );
    try {
      await navigator.clipboard.writeText(report);
    } catch {
      // Presse-papiers indisponible hors contexte sécurisé : repli historique
      const area = document.createElement("textarea");
      area.value = report;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  if (!caps) return null;
  const mark = (ok: boolean) => (
    <span style={{ color: ok ? "var(--accent-success)" : "var(--text-muted)", fontWeight: 600 }}>
      {ok ? t("browserCompat.yes") : t("browserCompat.no")}
    </span>
  );

  return (
    <section className="live-block" id="browser-compat-section">
      <h3>
        <Icon name="travel_explore" size={18} /> {t("browserCompat.section")}
      </h3>
      <p className="settings-hint" style={{ marginTop: 0 }}>{t("browserCompat.hint")}</p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
        <div>
          <strong>{t("browserCompat.codecsTitle")}</strong>
          <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0" }}>
            {caps.codecs.map((c) => (
              <li key={c.label} style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: "0.88rem" }}>
                <span>{c.label}</span>
                {mark(c.support !== "")}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <strong>{t("browserCompat.apisTitle")}</strong>
          <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0" }}>
            <li style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: "0.88rem" }}>
              <span>{t("browserCompat.secureContext")}</span>
              {mark(caps.secure)}
            </li>
            {caps.features.map((f) => (
              <li key={f.label} style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: "0.88rem" }}>
                <span>{f.label}</span>
                {mark(f.supported)}
              </li>
            ))}
          </ul>
          {!caps.secure && <p className="settings-hint">{t("browserCompat.secureContextHint")}</p>}
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <strong>{t("browserCompat.profileTitle")}</strong>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
          {(["auto", "web", "original"] as const).map((value) => (
            <button
              key={value}
              type="button"
              className={`btn btn-sm ${preference === value ? "btn-primary" : "btn-secondary"}`}
              aria-pressed={preference === value}
              onClick={() => changePreference(value)}
            >
              {t(value === "auto" ? "browserCompat.profileAuto" : value === "web" ? "browserCompat.profileWeb" : "browserCompat.profileOriginal")}
            </button>
          ))}
        </div>
        <p className="settings-hint">{t("browserCompat.profileHint")}</p>
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
        <input type="checkbox" checked={autoGenerate} onChange={(e) => toggleAutoGenerate(e.target.checked)} />
        {t("browserCompat.autoGenerate")}
      </label>
      <p className="settings-hint">{t("browserCompat.autoGenerateHint")}</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
        <button type="button" className="btn btn-secondary btn-sm" disabled={testState.running} onClick={runPlaybackTest}>
          {testState.running ? t("browserCompat.testing") : t("browserCompat.testButton")}
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={copyReport}>
          <Icon name="content_copy" size={14} /> {copied ? t("browserCompat.reportCopied") : t("browserCompat.copyReport")}
        </button>
        {testState.text && <span style={{ fontSize: "0.85rem" }}>{testState.text}</span>}
      </div>

      <details style={{ marginTop: 12 }}>
        <summary>{t("browserCompat.tipsTitle")}</summary>
        <ul className="settings-hint" style={{ paddingLeft: 18 }}>
          <li>{t("browserCompat.tipLinux")}</li>
          <li>{t("browserCompat.tipWindows")}</li>
          <li>{t("browserCompat.tipMac")}</li>
          <li>{t("browserCompat.tipAndroid")}</li>
        </ul>
      </details>
    </section>
  );
}
