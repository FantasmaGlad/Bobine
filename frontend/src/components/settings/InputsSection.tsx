"use client";

import { useCallback, useState } from "react";
import Icon from "@/components/Icon";
import InputRowView from "@/components/settings/inputs/InputRowView";
import { useInputCapture } from "@/components/settings/inputs/useInputCapture";
import { useRemoteInputs } from "@/components/settings/inputs/useRemoteInputs";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { inputRows, type InputKind } from "@/lib/inputSource";
import type { ShowToast } from "@/lib/useToast";

const GROUPS: readonly InputKind[] = ["key", "code", "pad"];

export default function InputsSection({ hidden, showToast }: { hidden: boolean; showToast: ShowToast }) {
  const { t } = useAppSettings();
  const onError = useCallback((message: string) => showToast(t("settingsPage.inputs.error", { message }), "error"), [showToast, t]);
  const { inputs, failed, bind, reset } = useRemoteInputs(onError);
  const [capturing, setCapturing] = useState(false);
  const save = useCallback(async (input: string, actions: Parameters<typeof bind>[1]) => {
    if (await bind(input, actions)) showToast(t("settingsPage.inputs.saved"), "success");
  }, [bind, showToast, t]);
  const onCapture = useCallback((source: string) => {
    setCapturing(false);
    const reveal = () => window.setTimeout(() => document.getElementById(`input-${source}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 0);
    if (inputs && !(source in inputs.bindings) && !(source in inputs.overrides)) void save(source, []).then(reveal);
    else reveal();
  }, [inputs, save]);
  useInputCapture(capturing, onCapture);

  const rows = inputs ? inputRows(inputs.bindings, inputs.overrides) : [];
  return (
    <section className="live-block inputs-section" id="section-inputs" hidden={hidden}>
      <h3><Icon name="sports_esports" size={18} /> {t("settingsPage.inputs.title")}</h3>
      <p className="settings-hint">{t("settingsPage.inputs.hint")}</p>
      {failed && <div className="live-empty">{t("settingsPage.inputs.loadError")}</div>}
      {inputs && (
        <>
          <div className="inputs-toolbar">
            {capturing ? (
              <>
                <span className="inputs-capture" role="status">{t("settingsPage.inputs.capturing")}</span>
                <button type="button" className="btn btn-secondary" onClick={() => setCapturing(false)}>{t("settingsPage.inputs.cancel")}</button>
              </>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => setCapturing(true)}>
                <Icon name="add" size={16} /> {t("settingsPage.inputs.add")}
              </button>
            )}
            <button type="button" className="btn btn-secondary" onClick={() => { if (window.confirm(t("settingsPage.inputs.resetConfirm"))) void reset(); }}>
              <Icon name="restart_alt" size={16} /> {t("settingsPage.inputs.reset")}
            </button>
          </div>
          {GROUPS.map((kind) => {
            const group = rows.filter((row) => row.kind === kind);
            if (group.length === 0) return null;
            return (
              <div key={kind} className="inputs-group">
                <h4>{t(`settingsPage.inputs.groups.${kind}`)}</h4>
                <ul className="inputs-list">
                  {group.map((row) => (
                    <InputRowView key={row.source} row={row} actions={inputs.actions} t={t} onBind={(actions) => void save(row.source, actions)} />
                  ))}
                </ul>
              </div>
            );
          })}
        </>
      )}
    </section>
  );
}
