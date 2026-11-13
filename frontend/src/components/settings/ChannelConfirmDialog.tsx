"use client";
import React from "react";
import { channelI18nSuffix, channelLogoUrl, type UpdateChannel } from "@/lib/releaseChannel";

interface ChannelConfirmDialogProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  confirmingChannel: UpdateChannel;
  changingChannel: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function ChannelConfirmDialog({ t, confirmingChannel, changingChannel, onCancel, onConfirm }: ChannelConfirmDialogProps) {
  return (
          <div className="modal-overlay">
            <div className="modal-content">
              <img
                src={channelLogoUrl(confirmingChannel)}
                alt=""
                width={72}
                height={72}
                style={{ display: "block", margin: "0 auto", borderRadius: "var(--radius-md)" }}
              />
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)", textAlign: "center" }}>
                {t("settingsPage.updateChannelConfirmTitle", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(confirmingChannel)}`) })}
              </h3>
              <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                {t(`settingsPage.updateChannelConfirmWarning${channelI18nSuffix(confirmingChannel)}`)}
              </p>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={changingChannel}>{t("common.cancel")}</button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={changingChannel}
                  onClick={onConfirm}
                >
                  {t("settingsPage.updateChannelConfirmButton", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(confirmingChannel)}`) })}
                </button>
              </div>
            </div>
          </div>
  );
}
