"use client";

import Icon from "@/components/Icon";
import { describeBalance, describeChannels, formatLatency, formatSampleRate, sliderFromBalance, balanceFromSlider } from "@/lib/devices/audio";
import { type AudioDetails, type AudioDevice } from "@/lib/devices/types";
import { type SectionProps } from "../../common";
import { type AudioDetailActions, type Tone } from "./useAudioDetailActions";

type T = SectionProps["t"];

export function BalanceBlock({ balance, actions, t }: { balance: number; actions: AudioDetailActions; t: T }) {
  const { sliding, setSliding, commitBalance } = actions;
  const shown = sliding !== null ? balanceFromSlider(sliding) : balance;
  const described = describeBalance(shown);
  return (
    <section className="dv-detail-block">
      <h4>{t("devices.audio.detail.balance")}</h4>
      <div className="dv-balance">
        <span className="dv-balance-side">{t("devices.audio.detail.left")}</span>
        <input
          type="range"
          min={-100}
          max={100}
          step={1}
          value={sliding ?? sliderFromBalance(balance)}
          aria-label={t("devices.audio.detail.balance")}
          onChange={(e) => setSliding(Number(e.target.value))}
          onMouseUp={() => sliding !== null && commitBalance(sliding)}
          onTouchEnd={() => sliding !== null && commitBalance(sliding)}
          onKeyUp={() => sliding !== null && commitBalance(sliding)}
        />
        <span className="dv-balance-side">{t("devices.audio.detail.right")}</span>
      </div>
      <div className="dv-balance-read">
        <span>
          {described?.side === "center" && t("devices.audio.detail.centered")}
          {described?.side === "left" && t("devices.audio.detail.rightAt", { percent: described.percent })}
          {described?.side === "right" && t("devices.audio.detail.leftAt", { percent: described.percent })}
        </span>
        <button type="button" className="dv-link-btn" disabled={balance === 0 && sliding === null} onClick={() => commitBalance(0)}>
          <Icon name="align_horizontal_center" size={14} /> {t("devices.audio.detail.center")}
        </button>
      </div>
    </section>
  );
}

const TONES: Tone[] = ["left", "both", "right"];

function toneIcon(channel: Tone): string {
  if (channel === "both") return "speaker";
  return channel === "left" ? "arrow_back" : "arrow_forward";
}

export function ToneBlock({ actions, t }: { actions: AudioDetailActions; t: T }) {
  const { playing, playTone } = actions;
  return (
    <section className="dv-detail-block">
      <h4>{t("devices.audio.detail.test")}</h4>
      <div className="dv-tone-row">
        {TONES.map((channel) => (
          <button key={channel} type="button" className={`btn btn-secondary dv-tone ${playing === channel ? "playing" : ""}`} disabled={playing !== null} onClick={() => playTone(channel)}>
            {playing === channel ? <span className="dv-wave" aria-hidden="true"><i /><i /><i /><i /></span> : <Icon name={toneIcon(channel)} size={16} />}
            {t(`devices.audio.detail.tone.${channel}`)}
          </button>
        ))}
      </div>
      <p className="settings-hint" style={{ margin: 0 }}>{t("devices.audio.detail.testHint")}</p>
    </section>
  );
}

function stateLabel(state: string, t: T): string {
  const key = `devices.audio.detail.states.${state}`;
  return t(key) === key ? state : t(key);
}

function detailRows(details: AudioDetails, t: T): [string, string][] {
  return [
    [t("devices.audio.detail.state"), stateLabel(details.state, t)],
    [t("devices.audio.detail.channels"), describeChannels(details.channels, details.channel_map, t)],
    [t("devices.audio.detail.rate"), formatSampleRate(details.sample_rate)],
    [t("devices.audio.detail.format"), details.format ?? "—"],
    [t("devices.audio.detail.latency"), formatLatency(details.latency_ms)],
    [t("devices.audio.detail.card"), details.card || "—"],
    [t("devices.audio.detail.connection"), [details.bus, details.api].filter(Boolean).join(" · ") || "—"],
    ...(details.codec ? [[t("devices.audio.detail.codec"), details.codec] as [string, string]] : []),
  ];
}

export function AnalysisBlock({ details, failed, t }: { details: AudioDetails | null; failed: string | null; t: T }) {
  return (
    <section className="dv-detail-block">
      <h4>{t("devices.audio.detail.analysis")}</h4>
      {!details && !failed && <p className="rl-empty-note">{t("devices.loading")}</p>}
      {details && (
        <dl className="dv-defs">
          {detailRows(details, t).map(([label, value]) => (
            <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
          ))}
        </dl>
      )}
      {details?.supported === false && <p className="rl-empty-note">{details.reason}</p>}
    </section>
  );
}

export function ProfileBlock({ details, actions, t }: { details: AudioDetails; actions: AudioDetailActions; t: T }) {
  return (
    <section className="dv-detail-block">
      <h4>{t("devices.audio.detail.profile")}</h4>
      <div className="dv-profiles" role="radiogroup" aria-label={t("devices.audio.detail.profile")}>
        {details.profiles.map((profile) => (
          <button
            key={profile.index}
            type="button"
            role="radio"
            aria-checked={profile.active}
            disabled={!profile.available}
            className={`dv-profile glass-interactive ${profile.active ? "is-selected" : ""}`}
            onClick={async () => { if (!profile.active) await actions.selectProfile(profile.index); }}
          >
            <span>{profile.name}</span>
            {profile.active && <Icon name="check_circle" size={18} filled />}
            {!profile.available && <span className="dv-sub">{t("devices.audio.detail.unavailable")}</span>}
          </button>
        ))}
      </div>
    </section>
  );
}

export function NameBlock({ device, actions, t }: { device: AudioDevice; actions: AudioDetailActions; t: T }) {
  const { alias, setAlias, saveAlias, toggleHidden } = actions;
  return (
    <section className="dv-detail-block">
      <h4>{t("devices.audio.detail.nameAndVisibility")}</h4>
      <form className="dv-password" onSubmit={(e) => { e.preventDefault(); void saveAlias(); }}>
        <input
          type="text"
          className="form-control"
          maxLength={60}
          value={alias}
          placeholder={device.name}
          aria-label={t("devices.audio.detail.customName")}
          onChange={(e) => setAlias(e.target.value)}
          onBlur={() => void saveAlias()}
        />
        <button type="submit" className="btn btn-secondary">{t("devices.audio.detail.save")}</button>
      </form>
      <button type="button" className="dv-link-btn" onClick={toggleHidden}>
        <Icon name={device.hidden ? "visibility" : "visibility_off"} size={14} /> {device.hidden ? t("devices.audio.detail.show") : t("devices.audio.detail.hide")}
      </button>
    </section>
  );
}
