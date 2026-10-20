"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import {
  audioDisplayName,
  audioKindIcon,
  balanceFromSlider,
  describeBalance,
  describeChannels,
  devicesRequest,
  formatLatency,
  formatSampleRate,
  sliderFromBalance,
  type AudioDetails,
  type AudioDevice,
} from "@/lib/devicesApi";
import { errorText, type SectionProps } from "./common";

interface Props extends Pick<SectionProps, "caps" | "notify" | "t"> {
  device: AudioDevice | null;
  onClose: () => void;
  /** Relire la liste des sorties (alias, masquage, volume ont pu changer). */
  onChanged: () => void;
}

type Tone = "left" | "right" | "both";

/** Détail d'une sortie : niveau, balance, son de test, analyse, profil, nom et visibilité. */
export default function AudioDetailSheet({ device, caps, notify, t, onClose, onChanged }: Props) {
  const id = device?.id ?? null;
  const [details, setDetails] = useState<AudioDetails | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [sliding, setSliding] = useState<number | null>(null);
  const [playing, setPlaying] = useState<Tone | null>(null);
  const [alias, setAlias] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    const result = await devicesRequest<AudioDetails>(`/audio/details?id=${encodeURIComponent(id)}`);
    if (result.ok) {
      setDetails(result.data);
      setFailed(null);
    } else {
      setFailed(errorText(result.error, t));
    }
  }, [id, t]);

  // Relecture toutes les 2 s tant que le tiroir est ouvert (état, niveau, balance changés ailleurs).
  useEffect(() => {
    if (!id) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement d'une ressource externe (API) à l'ouverture
    setDetails(null);
    setFailed(null);
    void load();
    const timer = setInterval(() => { void load(); }, 2000);
    return () => clearInterval(timer);
  }, [id, load]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reprend l'alias enregistré à l'ouverture
    setAlias(device?.alias ?? "");
  }, [device?.id, device?.alias]);

  const call = async (path: string, body: unknown, method = "POST") => {
    const result = await devicesRequest(path, { method, body });
    if (!result.ok) notify(errorText(result.error, t), "error");
    return result.ok;
  };

  if (!device) return null;
  const can = (key: string) => caps[key]?.supported === true;
  const balance = details?.balance ?? null;
  const shownBalance = sliding !== null ? balanceFromSlider(sliding) : balance;
  const described = shownBalance !== null ? describeBalance(shownBalance) : null;

  const commitBalance = async (value: number) => {
    const ok = await call("/audio/balance", { id: device.id, balance: balanceFromSlider(value) });
    setSliding(null);
    if (ok) await load();
  };

  const playTone = async (channel: Tone) => {
    setPlaying(channel);
    await call("/audio/test", { id: device.id, channel });
    setPlaying(null);
  };

  const saveAlias = async () => {
    if ((alias.trim() || null) === (device.alias ?? null)) return;
    if (await call("/audio/meta", { id: device.id, alias: alias.trim() }, "PUT")) {
      notify(t("devices.audio.detail.nameSaved"), "success");
      onChanged();
    }
  };

  const toggleHidden = async () => {
    const hide = !device.hidden;
    if (await call("/audio/meta", { id: device.id, hidden: hide }, "PUT")) {
      notify(hide ? t("devices.audio.detail.nowHidden") : t("devices.audio.detail.nowShown"), "success");
      onChanged();
      if (hide) onClose();
    }
  };

  const rows: [string, string][] = details
    ? [
        [t("devices.audio.detail.state"), t(`devices.audio.detail.states.${details.state}`) === `devices.audio.detail.states.${details.state}` ? details.state : t(`devices.audio.detail.states.${details.state}`)],
        [t("devices.audio.detail.channels"), describeChannels(details.channels, details.channel_map)],
        [t("devices.audio.detail.rate"), formatSampleRate(details.sample_rate)],
        [t("devices.audio.detail.format"), details.format ?? "—"],
        [t("devices.audio.detail.latency"), formatLatency(details.latency_ms)],
        [t("devices.audio.detail.card"), details.card || "—"],
        [t("devices.audio.detail.connection"), [details.bus, details.api].filter(Boolean).join(" · ") || "—"],
        ...(details.codec ? [[t("devices.audio.detail.codec"), details.codec] as [string, string]] : []),
      ]
    : [];

  return (
    <Sheet open onClose={onClose} tall title={audioDisplayName(device)} closeLabel={t("devices.audio.detail.close")}>
      <div className="dv-detail">
        <div className="dv-detail-head">
          <span className="dv-icon"><Icon name={audioKindIcon(device.kind)} size={24} /></span>
          <span className="dv-sub">
            {t(`devices.audio.kind.${device.kind}`)}
            {device.manufacturer ? ` · ${device.manufacturer}` : ""}
            {device.alias ? ` · ${device.name}` : ""}
          </span>
          {device.is_default && <span className="dv-badge">{t("devices.audio.default")}</span>}
        </div>

        {failed && <div className="dv-note"><Icon name="error" size={16} /><span>{failed}</span></div>}

        {can("audio_balance") && balance !== null && (
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
        )}

        {can("audio_test_tone") && (
          <section className="dv-detail-block">
            <h4>{t("devices.audio.detail.test")}</h4>
            <div className="dv-tone-row">
              {(["left", "both", "right"] as Tone[]).map((channel) => (
                <button key={channel} type="button" className={`btn btn-secondary dv-tone ${playing === channel ? "playing" : ""}`} disabled={playing !== null} onClick={() => playTone(channel)}>
                  {playing === channel ? <span className="dv-wave" aria-hidden="true"><i /><i /><i /><i /></span> : <Icon name={channel === "both" ? "speaker" : channel === "left" ? "arrow_back" : "arrow_forward"} size={16} />}
                  {t(`devices.audio.detail.tone.${channel}`)}
                </button>
              ))}
            </div>
            <p className="settings-hint" style={{ margin: 0 }}>{t("devices.audio.detail.testHint")}</p>
          </section>
        )}

        <section className="dv-detail-block">
          <h4>{t("devices.audio.detail.analysis")}</h4>
          {!details && !failed && <p className="rl-empty-note">{t("devices.loading")}</p>}
          {details && (
            <dl className="dv-defs">
              {rows.map(([label, value]) => (
                <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
              ))}
            </dl>
          )}
          {details?.supported === false && <p className="rl-empty-note">{details.reason}</p>}
        </section>

        {can("audio_profile") && details && details.profiles.length > 0 && (
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
                  onClick={async () => { if (!profile.active && (await call("/audio/profile", { id: device.id, index: profile.index }))) { await load(); onChanged(); } }}
                >
                  <span>{profile.name}</span>
                  {profile.active && <Icon name="check_circle" size={18} filled />}
                  {!profile.available && <span className="dv-sub">{t("devices.audio.detail.unavailable")}</span>}
                </button>
              ))}
            </div>
          </section>
        )}

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
      </div>
    </Sheet>
  );
}
