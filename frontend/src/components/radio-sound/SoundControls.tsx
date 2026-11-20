import { BAND_FREQUENCIES, BAND_GAIN_MAX_DB, BAND_GAIN_MIN_DB, BASS_BOOST_MAX_DB, PRESETS, applyPreset, defaultSound, type RadioSoundSettings } from "@/lib/radioSound";

type T = (key: string, params?: Record<string, string | number>) => string;

interface ControlProps {
  current: RadioSoundSettings;
  commit: (next: RadioSoundSettings) => void;
  setManual: (patch: Partial<RadioSoundSettings>) => void;
  t: T;
}

export function formatFrequency(hz: number): string {
  return hz >= 1000 ? `${hz / 1000} kHz` : `${hz} Hz`;
}

export function formatGain(db: number): string {
  return `${db > 0 ? "+" : ""}${db} dB`;
}

export function PresetChips({ current, commit, activePreset, t }: ControlProps & { activePreset: string | null | undefined }) {
  return (
    <div className="radio-sound-presets" role="group" aria-label={t("radioSound.presetsLabel")}>
      {PRESETS.map((preset) => (
        <button
          key={preset.id}
          type="button"
          className={`radio-sound-chip olc-press ${activePreset === preset.id ? "active" : ""}`}
          aria-pressed={activePreset === preset.id}
          disabled={!current.enabled}
          onClick={() => commit(applyPreset(preset.id, current))}
        >
          {t(`radioSound.presets.${preset.id}`)}
        </button>
      ))}
    </div>
  );
}

export function BandSliders({ current, setManual, t }: ControlProps) {
  return (
    <div className="radio-sound-bands" aria-label={t("radioSound.bandsLabel")}>
      {BAND_FREQUENCIES.map((frequency, i) => (
        <label key={frequency} className="radio-sound-row">
          <span className="radio-sound-row-label">{formatFrequency(frequency)}</span>
          <input
            type="range"
            min={BAND_GAIN_MIN_DB}
            max={BAND_GAIN_MAX_DB}
            step={1}
            value={current.bands[i]}
            disabled={!current.enabled}
            onChange={(e) => {
              const bands = [...current.bands];
              bands[i] = Number(e.target.value);
              setManual({ bands });
            }}
            className="volume-slider"
            aria-label={`${formatFrequency(frequency)}`}
          />
          <span className="radio-sound-row-value">{formatGain(current.bands[i])}</span>
        </label>
      ))}
    </div>
  );
}

export function BassSlider({ current, setManual, t }: ControlProps) {
  return (
    <label className="radio-sound-row">
      <span className="radio-sound-row-label">{t("radioSound.bass")}</span>
      <input
        type="range"
        min={0}
        max={BASS_BOOST_MAX_DB}
        step={1}
        value={current.bass_boost}
        disabled={!current.enabled}
        onChange={(e) => setManual({ bass_boost: Number(e.target.value) })}
        className="volume-slider"
        aria-label={t("radioSound.bass")}
      />
      <span className="radio-sound-row-value">{formatGain(current.bass_boost)}</span>
    </label>
  );
}

export function SoundToggles({ current, commit, setManual, t }: ControlProps) {
  return (
    <div className="radio-sound-toggles">
      <label className="radio-sound-switch" title={t("radioSound.loudnessHint")}>
        <input type="checkbox" checked={current.loudness} disabled={!current.enabled} onChange={(e) => setManual({ loudness: e.target.checked })} />
        <span>{t("radioSound.loudness")}</span>
      </label>
      <label className="radio-sound-switch" title={t("radioSound.limiterHint")}>
        <input type="checkbox" checked={current.limiter} disabled={!current.enabled} onChange={(e) => commit({ ...current, limiter: e.target.checked })} />
        <span>{t("radioSound.limiter")}</span>
      </label>
      <button type="button" className="btn btn-secondary radio-sound-reset" onClick={() => commit({ ...defaultSound(), limiter: current.limiter })}>
        {t("radioSound.reset")}
      </button>
    </div>
  );
}
