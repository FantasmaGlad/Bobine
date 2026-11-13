"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { TargetType } from "@/lib/scheduleTime";

import TargetPicker from "./TargetPicker";
import type { ScheduleCatalog } from "./useScheduleData";
import type { ScheduleFormState } from "./useScheduleForm";
import WhenFields from "./WhenFields";

interface Props {
  radio: boolean;
  catalog: ScheduleCatalog;
  state: ScheduleFormState;
}

function TargetTypeSwitch({ state }: { state: ScheduleFormState }) {
  const { t } = useAppSettings();
  const button = (type: TargetType, label: string) => (
    <button type="button" className={`speed-btn ${state.form.targetType === type ? "active" : ""}`} style={{ flex: 1 }} onClick={() => state.patch({ targetType: type, targetId: "" })}>
      {t(label)}
    </button>
  );
  return (
    <div className="speed-group" style={{ width: "100%" }}>
      {button("video", "schedule.videoOption")}
      {button("playlist", "schedule.playlistOption")}
    </div>
  );
}

function Actions({ state }: { state: ScheduleFormState }) {
  const { t } = useAppSettings();
  return (
    <div className="drawer-actions">
      <button type="submit" className="btn btn-primary" disabled={state.saving}>
        {state.saving ? t("common.saving") : t("common.save")}
      </button>
      <button type="button" className="btn btn-secondary" onClick={state.close} disabled={state.saving}>
        {t("common.cancel")}
      </button>
      {state.editingId && (
        <button type="button" className="btn btn-danger" onClick={() => state.setConfirmDelete(true)} disabled={state.saving}>
          {t("schedule.deleteScheduleBtn")}
        </button>
      )}
    </div>
  );
}

export default function ScheduleDrawer({ radio, catalog, state }: Props) {
  const { t } = useAppSettings();
  return (
    <>
      <div className="detail-drawer-overlay" onClick={state.close} />
      <div className="detail-drawer">
        <div className="drawer-header">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>
            {state.editingId ? t("schedule.editScheduleTitle") : t("schedule.newScheduleTitle")}
          </h3>
          <button className="close-btn" onClick={state.close}>
            <Icon name="close" size={20} />
          </button>
        </div>
        <form onSubmit={state.save} className="drawer-body drawer-form">
          <div className="form-group">
            <label className="form-label">{radio ? t("schedule.radioPlaylistLabel") : t("schedule.targetLabel")}</label>
            {!radio && <TargetTypeSwitch state={state} />}
          </div>
          <TargetPicker radio={radio} catalog={catalog} state={state} />
          <WhenFields state={state} />
          {state.editingId && state.overrideCount > 0 && (
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{t("schedule.overrideCountHint", { count: state.overrideCount })}</p>
          )}
          <Actions state={state} />
        </form>
      </div>
    </>
  );
}

export function DeleteScheduleDialog({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  const { t } = useAppSettings();
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 style={{ fontSize: "1.1rem", margin: "0 0 12px" }}>{t("schedule.deleteScheduleTitle")}</h3>
        <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: "0 0 20px", lineHeight: 1.5 }}>{t("schedule.deleteScheduleConfirm")}</p>
        <div className="modal-actions">
          <button className="btn btn-danger" onClick={onConfirm}>{t("common.delete")}</button>
          <button className="btn btn-secondary" onClick={onCancel}>{t("common.cancel")}</button>
        </div>
      </div>
    </div>
  );
}
