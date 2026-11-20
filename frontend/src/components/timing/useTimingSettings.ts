import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { TIMING_SETTING_KEYS, parseBounded, type TimingSettingKey } from "@/lib/settingsBounds";

export type TimingStatus = "idle" | "saved" | "error";
type Values<V> = Partial<Record<TimingSettingKey, V>>;

async function putSetting(key: TimingSettingKey, value: number) {
  const res = await fetch(getApiUrl("/settings"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [key]: value }),
  });
  if (!res.ok) throw new Error(String(res.status));
}

export function useTimingSettings() {
  const [saved, setSaved] = useState<Values<number>>({});
  const [draft, setDraft] = useState<Values<string>>({});
  const [status, setStatus] = useState<Values<TimingStatus>>({});

  const load = useCallback(() => fetch(getApiUrl("/settings"), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (!data) return;
      const values: Values<number> = {};
      for (const key of TIMING_SETTING_KEYS) if (typeof data[key] === "number") values[key] = data[key];
      setSaved(values);
    })
    .catch(() => {}), []);

  useEffect(() => {
    void load();
  }, [load]);

  const commit = async (key: TimingSettingKey) => {
    const text = draft[key];
    if (text === undefined) return;
    const value = parseBounded(key, text);
    if (value === null) return setStatus((s) => ({ ...s, [key]: "error" }));
    if (value === saved[key]) return setDraft((d) => ({ ...d, [key]: undefined }));
    try {
      await putSetting(key, value);
      setSaved((s) => ({ ...s, [key]: value }));
      setDraft((d) => ({ ...d, [key]: undefined }));
      setStatus((s) => ({ ...s, [key]: "saved" }));
    } catch {
      setStatus((s) => ({ ...s, [key]: "error" }));
    }
  };

  const edit = (key: TimingSettingKey, text: string) => {
    setDraft((d) => ({ ...d, [key]: text }));
    setStatus((s) => ({ ...s, [key]: "idle" }));
  };

  return { saved, draft, status, commit, edit };
}
