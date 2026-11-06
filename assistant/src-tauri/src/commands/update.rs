use serde::Serialize;
use tauri::{AppHandle, Emitter};
use tauri_plugin_updater::UpdaterExt;

/// Mise à jour de l'assistant lui-même, par le greffon officiel de Tauri : `latest.json` de la release de son canal
/// (`assistant-stable`, `assistant-beta` ou `assistant-canary`, cf. `scripts/bundle.py`), paquet vérifié avec la clé
/// publique de `tauri.conf.json` avant toute installation. Le greffon choisit l'installeur du paquet en place
/// (NSIS, `.app`, `.deb` ou `.rpm` ; les deux derniers demandent les droits par la fenêtre système).
#[derive(Debug, Clone, Serialize)]
pub struct AssistantUpdate {
    pub available: bool,
    pub current: String,
    pub version: Option<String>,
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct Progress {
    downloaded: u64,
    total: Option<u64>,
}

/// Message d'une recherche de mise à jour en échec ; une copie hors paquet (binaire brut, compilation locale) ne trouve
/// pas son installeur dans `latest.json` : elle se met à jour par un paquet, pas toute seule.
pub(crate) fn describe(error: tauri_plugin_updater::Error) -> String {
    match error {
        tauri_plugin_updater::Error::TargetNotFound(_) | tauri_plugin_updater::Error::TargetsNotFound(_) => {
            "Cette copie de l'assistant n'est pas installée par un paquet (.deb, .rpm, installeur Windows ou macOS) : \
             elle ne peut pas se mettre à jour seule. Installez le paquet de votre système depuis la release de l'assistant."
                .to_string()
        }
        other => other.to_string(),
    }
}

#[tauri::command]
pub async fn check_assistant_update(app: AppHandle) -> Result<AssistantUpdate, String> {
    let current = app.package_info().version.to_string();
    let update = app.updater().map_err(|e| e.to_string())?.check().await.map_err(describe)?;
    Ok(match update {
        Some(update) => AssistantUpdate {
            available: true,
            current,
            version: Some(update.version.clone()),
            notes: update.body.clone(),
        },
        None => AssistantUpdate { available: false, current, version: None, notes: None },
    })
}

/// Télécharge, vérifie, installe puis relance l'assistant ; la progression part en événements
/// `assistant-update-progress` (octets reçus, taille totale si connue).
#[tauri::command]
pub async fn install_assistant_update(app: AppHandle) -> Result<(), String> {
    let update = app
        .updater()
        .map_err(|e| e.to_string())?
        .check()
        .await
        .map_err(describe)?
        .ok_or_else(|| "Aucune mise à jour disponible.".to_string())?;
    let mut downloaded = 0u64;
    let emitter = app.clone();
    update
        .download_and_install(
            move |chunk, total| {
                downloaded += chunk as u64;
                let _ = emitter.emit("assistant-update-progress", Progress { downloaded, total });
            },
            || {},
        )
        .await
        .map_err(|e| e.to_string())?;
    app.restart();
}
