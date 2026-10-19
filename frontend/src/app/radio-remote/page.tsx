"use client";

import React, { useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { RadioChannelId } from "@/lib/displayChannel";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import Icon from "@/components/Icon";

// Télécommande admin des sorties radio : chaque sortie (câblée, réseau) a son propre moteur
// — playlist, file d'attente, volume, rappels, planning. Cette page n'est qu'un conteneur à
// onglets autour de la télécommande partagée (`RadioRemotePanel`), qui est AUSSI montée par la
// page « Sortie Câblé » quand l'écran câblé est en mode Radio. Le lecteur réel de chaque
// sortie est l'écran `/radio?channel=…`.

const STORAGE_KEY = "bobine.radioRemote.channel";

/** Dernière sortie consultée (confort par appareil). Tout accès au stockage est protégé :
 * il peut être indisponible (navigation privée, données bloquées) — la page reste correcte. */
function readStoredChannel(): RadioChannelId {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "radio_cable" || stored === "radio_network") return stored;
  } catch {
    // stockage indisponible : sortie réseau par défaut
  }
  return "radio_network";
}

function readRequestedChannel(): RadioChannelId | null {
  // Lien direct depuis la page « Sortie Câblé » ou Réglages : /radio-remote?channel=cable|network
  const requested = new URLSearchParams(window.location.search).get("channel");
  if (requested === "cable") return "radio_cable";
  if (requested === "network") return "radio_network";
  return null;
}

export default function RadioRemotePage() {
  const { t } = useAppSettings();
  // Sortie inconnue au rendu serveur (export statique) : la préférence locale est lue après
  // l'hydratation, et le panneau n'est monté qu'ensuite — une seule connexion WebSocket, pas une
  // première sur la sortie réseau aussitôt remplacée.
  const [channel, setChannel] = useState<RadioChannelId | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture unique d'une préférence locale après hydratation
    setChannel(readRequestedChannel() ?? readStoredChannel());
  }, []);

  const selectChannel = (next: RadioChannelId) => {
    setChannel(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // stockage indisponible : la sélection reste valable pour cette session
    }
  };

  return (
    <div className="dashboard-container">
      {/* Même barre que celle de la page « Sortie Câblé » (carte d'en-tête + commutateur en pilule) :
          une seule apparence pour tous les choix de sortie. */}
      <div className="live-block channel-card">
        <div className="channel-card-left">
          <h3>
            <Icon name="graphic_eq" size={18} />
            {t("radioRemote.title")}
          </h3>
          <span className="status-pill neutral">
            {channel === "radio_cable" ? t("radioRemote.outputCable") : t("radioRemote.outputNetwork")}
          </span>
        </div>
        <div className="channel-card-right">
          <div className="display-output-switch" role="tablist" aria-label={t("radioRemote.outputTabs")}>
            <span className="display-output-label">{t("radioRemote.outputTabs")}</span>
            <div className="display-output-buttons">
              <button
                role="tab"
                aria-selected={channel === "radio_cable"}
                className={`display-output-btn olc-press ${channel === "radio_cable" ? "active" : ""}`}
                onClick={() => selectChannel("radio_cable")}
                title={t("radioRemote.outputCableTitle")}
              >
                <Icon name="cable" size={16} />
                {t("radioRemote.outputCable")}
              </button>
              <button
                role="tab"
                aria-selected={channel === "radio_network"}
                className={`display-output-btn olc-press ${channel === "radio_network" ? "active" : ""}`}
                onClick={() => selectChannel("radio_network")}
                title={t("radioRemote.outputNetworkTitle")}
              >
                <Icon name="wifi" size={16} />
                {t("radioRemote.outputNetwork")}
              </button>
            </div>
          </div>
        </div>
      </div>
      {channel && <RadioRemotePanel key={channel} channel={channel} />}
    </div>
  );
}
