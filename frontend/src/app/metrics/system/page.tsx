"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import TelemetryHistoryDrawer from "@/components/TelemetryHistoryDrawer";

interface SystemTelemetry {
  cpu_percent: number;
  cpu_name?: string;
  cpu_temp_c?: number | null;
  gpu_percent?: number | null;
  gpu_name?: string | null;
  gpu_temp_c?: number | null;
  memory_total_bytes: number;
  memory_used_bytes: number;
  memory_percent: number;
  ram_brand?: string | null;
  ram_type?: string | null;
  ram_freq?: string | null;
  ram_model?: string | null;
  power_watts?: number | null;
  storage_model?: string;
  storage_used_percent?: number;
  storage_free_bytes?: number;
  storage_total_bytes?: number;
  storage?: {
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    used_percent: number;
  };
  runtime?: {
    uptime_seconds: number;
    uptime_formatted: string;
    app_runtime_seconds: number;
    app_runtime_formatted: string;
    cumulative_energy_wh?: number;
    average_power_watts?: number | null;
  };
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes < 0) return "0 Go";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const val = bytes / Math.pow(1024, i);
  return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function MetricsSystemPage() {
  const { t } = useAppSettings();
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);
  const [activeDrawer, setActiveDrawer] = useState<{
    metric: string;
    title: string;
    iconName: string;
  } | null>(null);

  const fetchTelemetry = useCallback(async () => {
    try {
      const res = await fetch("/api/settings/system", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setTelemetry(data);
      }
    } catch (err) {
      console.error("Erreur chargement télémétrie système:", err);
    }
  }, []);

  useEffect(() => {
    fetchTelemetry();
  }, [fetchTelemetry]);

  // Actualisation toutes les 5 secondes
  useEffect(() => {
    const id = setInterval(fetchTelemetry, 5000);
    return () => clearInterval(id);
  }, [fetchTelemetry]);

  const openDrawer = (metric: string, title: string, iconName: string) => {
    setActiveDrawer({ metric, title, iconName });
  };

  const handleKeyDown = (e: React.KeyboardEvent, metric: string, title: string, iconName: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openDrawer(metric, title, iconName);
    }
  };

  const freeStorage = telemetry?.storage_free_bytes ?? telemetry?.storage?.free_bytes ?? 0;
  const totalStorage = telemetry?.storage_total_bytes ?? telemetry?.storage?.total_bytes ?? 0;
  const usedStoragePct = telemetry?.storage_used_percent ?? telemetry?.storage?.used_percent ?? 0;

  return (
    <div className="metrics-page">
      {/* Grille principale de supervision matérielle */}
      <section className="metrics-section-card" style={{ marginTop: 0 }}>
        <div className="metrics-section-header">
          <div>
            <h3>
              <Icon name="monitor_heart" size={22} /> {t("metricsPage.telemetryTitle")}
            </h3>
            <p className="metrics-section-subtitle">
              Surveillance en direct des composants. Cliquez sur une métrique pour afficher son historique temporel.
            </p>
          </div>
        </div>

        <div className="metrics-telemetry-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
          {/* 1. CPU */}
          <div
            className="metrics-telemetry-item interactive"
            role="button"
            tabIndex={0}
            onClick={() => openDrawer("cpu", "Charge CPU", "memory")}
            onKeyDown={(e) => handleKeyDown(e, "cpu", "Charge CPU", "memory")}
            aria-label="Afficher l'historique de la charge CPU"
          >
            <div className="metrics-telemetry-item-head">
              <Icon name="memory" size={20} />
              <span className="metrics-telemetry-name">{t("metricsPage.cpu")}</span>
            </div>
            <span className="metrics-telemetry-component-name" title={telemetry?.cpu_name}>
              {telemetry?.cpu_name || "Processeur"}
            </span>
            <div className="metrics-telemetry-metric-val">
              <strong>{telemetry?.cpu_percent != null ? telemetry.cpu_percent.toFixed(0) : "0"}%</strong>
              {telemetry?.cpu_temp_c != null && (
                <span className="metrics-telemetry-temp">{telemetry.cpu_temp_c.toFixed(0)} °C</span>
              )}
            </div>
            <span className="metrics-telemetry-cta">
              Historique <Icon name="chevron_right" size={14} />
            </span>
          </div>

          {/* 2. GPU */}
          <div
            className="metrics-telemetry-item interactive"
            role="button"
            tabIndex={0}
            onClick={() => openDrawer("gpu", "Charge GPU", "videogame_asset")}
            onKeyDown={(e) => handleKeyDown(e, "gpu", "Charge GPU", "videogame_asset")}
            aria-label="Afficher l'historique de la puce graphique"
          >
            <div className="metrics-telemetry-item-head">
              <Icon name="videogame_asset" size={20} />
              <span className="metrics-telemetry-name">{t("metricsPage.gpu")}</span>
            </div>
            <span className="metrics-telemetry-component-name" title={telemetry?.gpu_name || "Puce Graphique"}>
              {telemetry?.gpu_name || "Puce Graphique"}
            </span>
            <div className="metrics-telemetry-metric-val">
              <strong>{telemetry?.gpu_percent != null ? telemetry.gpu_percent.toFixed(0) : "0"}%</strong>
              {telemetry?.gpu_temp_c != null && (
                <span className="metrics-telemetry-temp">{telemetry.gpu_temp_c.toFixed(0)} °C</span>
              )}
            </div>
            <span className="metrics-telemetry-cta">
              Historique <Icon name="chevron_right" size={14} />
            </span>
          </div>

          {/* 3. RAM */}
          <div
            className="metrics-telemetry-item interactive"
            role="button"
            tabIndex={0}
            onClick={() => openDrawer("memory", "Utilisation RAM", "developer_board")}
            onKeyDown={(e) => handleKeyDown(e, "memory", "Utilisation RAM", "developer_board")}
            aria-label="Afficher l'historique de la mémoire vive"
          >
            <div className="metrics-telemetry-item-head">
              <Icon name="developer_board" size={20} />
              <span className="metrics-telemetry-name">{t("metricsPage.ram")}</span>
            </div>
            <span
              className="metrics-telemetry-component-name"
              title={telemetry?.ram_model || (telemetry?.ram_type ? `${telemetry.ram_brand ? telemetry.ram_brand + " " : ""}${telemetry.ram_type}${telemetry.ram_freq ? " " + telemetry.ram_freq : ""}` : "Mémoire vive")}
            >
              {telemetry?.ram_model || (telemetry?.ram_type ? `${telemetry.ram_brand ? telemetry.ram_brand + " " : ""}${telemetry.ram_type}${telemetry.ram_freq ? " " + telemetry.ram_freq : ""}` : "Mémoire vive")}
            </span>
            <div className="metrics-telemetry-metric-val">
              <strong>{telemetry?.memory_percent != null ? telemetry.memory_percent.toFixed(0) : "0"}%</strong>
              <span className="metrics-telemetry-temp">
                {formatBytes(telemetry?.memory_used_bytes)} / {formatBytes(telemetry?.memory_total_bytes)}
              </span>
            </div>
            <span className="metrics-telemetry-cta">
              Historique <Icon name="chevron_right" size={14} />
            </span>
          </div>

          {/* 4. Stockage Principal */}
          <div
            className="metrics-telemetry-item interactive"
            role="button"
            tabIndex={0}
            onClick={() => openDrawer("storage", "Occupation Stockage", "storage")}
            onKeyDown={(e) => handleKeyDown(e, "storage", "Occupation Stockage", "storage")}
            aria-label="Afficher l'historique du stockage principal"
          >
            <div className="metrics-telemetry-item-head">
              <Icon name="storage" size={20} />
              <span className="metrics-telemetry-name">{t("metricsPage.storage")}</span>
            </div>
            <span className="metrics-telemetry-component-name" title={telemetry?.storage_model || "Disque principal"}>
              {telemetry?.storage_model || "Disque principal"}
            </span>
            <div className="metrics-telemetry-metric-val">
              <strong>{usedStoragePct.toFixed(0)}%</strong>
              <span className="metrics-telemetry-temp">
                {formatBytes(freeStorage)} libres sur {formatBytes(totalStorage)}
              </span>
            </div>
            <span className="metrics-telemetry-cta">
              Historique <Icon name="chevron_right" size={14} />
            </span>
          </div>

          {/* 5. Puissance & Énergie */}
          <div
            className="metrics-telemetry-item interactive"
            role="button"
            tabIndex={0}
            onClick={() => openDrawer("power", "Puissance consommée", "bolt")}
            onKeyDown={(e) => handleKeyDown(e, "power", "Puissance consommée", "bolt")}
            aria-label="Afficher l'historique de la puissance et de l'énergie consommée"
          >
            <div className="metrics-telemetry-item-head">
              <Icon name="bolt" size={20} style={{ color: "var(--accent-primary)" }} />
              <span className="metrics-telemetry-name">{t("metricsPage.power")} & Énergie</span>
            </div>
            <span className="metrics-telemetry-component-name">
              {telemetry?.runtime?.cumulative_energy_wh != null
                ? `Cumul: ${telemetry.runtime.cumulative_energy_wh.toFixed(1)} Wh · Moy: ${telemetry.runtime.average_power_watts != null ? telemetry.runtime.average_power_watts.toFixed(1) + " W" : "--"}`
                : "Alimentation système"}
            </span>
            <div className="metrics-telemetry-metric-val">
              <strong style={{ color: "var(--accent-primary)" }}>
                {telemetry?.power_watts != null ? `${telemetry.power_watts.toFixed(1)} W` : "-- W"}
              </strong>
            </div>
            <span className="metrics-telemetry-cta">
              Historique <Icon name="chevron_right" size={14} />
            </span>
          </div>

          {/* 6. Uptime Système & Runtime Service */}
          <div className="metrics-telemetry-item">
            <div className="metrics-telemetry-item-head">
              <Icon name="timer" size={20} />
              <span className="metrics-telemetry-name">{t("metricsPage.runtime")}</span>
            </div>
            <span className="metrics-telemetry-component-name">
              Uptime Système : {telemetry?.runtime?.uptime_formatted || "--"}
            </span>
            <div className="metrics-telemetry-metric-val">
              <span style={{ fontSize: "0.92rem", fontWeight: 700, color: "var(--accent-primary)" }}>
                Service : {telemetry?.runtime?.app_runtime_formatted || "--"}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Tiroir latéral d'historique avec graphique temporel */}
      {activeDrawer && (
        <TelemetryHistoryDrawer
          isOpen={true}
          onClose={() => setActiveDrawer(null)}
          metric={activeDrawer.metric}
          title={activeDrawer.title}
          iconName={activeDrawer.iconName}
        />
      )}
    </div>
  );
}
