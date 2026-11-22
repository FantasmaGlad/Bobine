"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import DangerConfirmModal from "./DangerConfirmModal";
import { useResetData, useUninstall } from "./useDangerActions";

const UNINSTALL_PHRASE = "DÉSINSTALLER";
const RESET_DATA_PHRASE = "RÉINITIALISER";

const UNINSTALL_HINTS: Record<string, string> = {
  windows: "settingsPage.uninstallDesktopWindows",
  macos: "settingsPage.uninstallDesktopMacos",
  android: "settingsPage.uninstallDesktopAndroid",
};
const MANUAL_HINTS: Record<string, string> = {
  windows: "settingsPage.uninstallManualHintWindows",
  macos: "settingsPage.uninstallManualHintMacos",
  android: "settingsPage.uninstallManualHintAndroid",
};

type ToastType = "success" | "error" | "warning";

interface DangerSectionProps {
  hidden: boolean;
  deploymentProfile: string;
  showToast: (message: string, type?: ToastType) => void;
}

function DangerCard({ icon, title, hint, action, onAction, children }: {
  icon: string; title: string; hint: string; action: string; onAction: () => void; children?: React.ReactNode;
}) {
  return (
    <div className="settings-danger-card">
      <h4>
        <Icon name={icon} size={18} /> {title}
      </h4>
      <p>{hint}</p>
      <div>
        <button type="button" className="btn btn-danger" onClick={onAction}>
          <Icon name={icon} size={16} /> {action}
        </button>
      </div>
      {children}
    </div>
  );
}

export default function DangerSection({ hidden, deploymentProfile, showToast }: DangerSectionProps) {
  const { t } = useAppSettings();
  const uninstall = useUninstall(showToast);
  const reset = useResetData(showToast);

  return (
    <>
      <section className="live-block settings-danger" id="section-danger" hidden={hidden}>
        <h3 style={{ margin: "0 0 6px 0" }}>
          <Icon name="warning" size={18} /> {t("settingsPage.dangerSection")}
        </h3>
        <p className="settings-hint" style={{ margin: "0 0 16px 0" }}>
          {t("settingsPage.dangerHint")}
        </p>
        <div className="settings-danger-group">
          <DangerCard icon="cleaning_services" title={t("settingsPage.resetDataTitle")} hint={t("settingsPage.resetDataHint")}
            action={t("settingsPage.resetDataAction")} onAction={() => reset.setOpen(true)} />
          <hr className="settings-danger-separator" />
          <DangerCard icon="delete_forever" title={t("settingsPage.uninstallSectionTitle")}
            hint={t(UNINSTALL_HINTS[deploymentProfile] ?? "settingsPage.uninstallDesktopLinux")}
            action={t("settingsPage.uninstallAction")} onAction={() => uninstall.setOpen(true)}>
            <div className="settings-danger-manual">
              {t(MANUAL_HINTS[deploymentProfile] ?? "settingsPage.uninstallManualHintLinux")}
            </div>
          </DangerCard>
        </div>
      </section>

      {uninstall.open && (
        <DangerConfirmModal icon="delete_forever" title={t("settingsPage.uninstallButton")} text={t("settingsPage.uninstallConfirmText")}
          items={[t("settingsPage.uninstallItemServices"), t("settingsPage.uninstallItemApp"), t("settingsPage.uninstallItemData"), t("settingsPage.uninstallItemKeepPackages")]}
          phraseLabel={t("settingsPage.uninstallTypeLabel", { phrase: UNINSTALL_PHRASE })} phrase={UNINSTALL_PHRASE}
          value={uninstall.confirm} onChange={uninstall.setConfirm} onCancel={uninstall.cancel} onConfirm={uninstall.run}
          ready={uninstall.ready} busy={uninstall.busy}
          busyLabel={t("settingsPage.uninstallInProgress")} confirmLabel={t("settingsPage.uninstallConfirmButton")} />
      )}

      {reset.open && (
        <DangerConfirmModal icon="cleaning_services" title={t("settingsPage.resetDataButton")} text={t("settingsPage.resetDataConfirmText")}
          items={[t("settingsPage.resetDataItemMedia"), t("settingsPage.resetDataItemDb"), t("settingsPage.resetDataItemKeepApp")]}
          phraseLabel={t("settingsPage.resetDataTypeLabel", { phrase: RESET_DATA_PHRASE })} phrase={RESET_DATA_PHRASE}
          value={reset.confirm} onChange={reset.setConfirm} onCancel={reset.cancel} onConfirm={reset.run}
          ready={reset.ready} busy={reset.busy}
          busyLabel={t("settingsPage.resetDataInProgress")} confirmLabel={t("settingsPage.resetDataConfirmButton")} />
      )}
    </>
  );
}
