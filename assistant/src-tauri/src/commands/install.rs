use std::io::{BufRead, BufReader};
use std::net::TcpStream;
use std::time::Duration;
use serde::{Deserialize, Serialize};
use ssh2::Session;
use tauri::Emitter;

use bobine_installer_core::orchestrate::{build_remote_command, Elevation, InstallOptions as CoreOptions};
use bobine_installer_core::progress::{classify_line, LineKind, Phase, ProgressState};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunInstallParams {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: Option<String>,
    pub root_password: Option<String>,
    pub elevation_strategy: String,
    pub script_path: Option<String>,
    pub no_kiosk: bool,
    pub skip_packages: bool,
    pub mock_replay: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressUpdate {
    pub pct: u8,
    pub step_index: u32,
    pub total_steps: u32,
    pub step_title: String,
    pub step_slug: String,
    pub phase: String,
    pub error_message: Option<String>,
    pub access_url: Option<String>,
}

fn progress_to_update(state: &ProgressState) -> ProgressUpdate {
    let phase_str = match state.phase {
        Phase::NotStarted => "not_started",
        Phase::Running => "running",
        Phase::Succeeded => "succeeded",
        Phase::Failed => "failed",
    };

    let (step_idx, step_title, step_slug) = if let Some(ref cur) = state.current {
        (cur.index, cur.title.clone(), cur.slug.clone())
    } else {
        (0, "Initialisation...".to_string(), "init".to_string())
    };

    let error_message = state
        .failure
        .as_ref()
        .map(|f| format!("Échec à l'étape {} ({}) : {}", f.index, f.slug, f.title));

    let access_url = state.end.as_ref().and_then(|e| e.url.clone());

    ProgressUpdate {
        pct: state.pct,
        step_index: step_idx,
        total_steps: state.total,
        step_title,
        step_slug,
        phase: phase_str.to_string(),
        error_message,
        access_url,
    }
}

/// Simulation d'installation basée sur la fixture réelle enregistrée
async fn run_mock_installation(app: tauri::AppHandle) -> Result<(), String> {
    // Évènements réels enregistrés lors d'une exécution de install.sh
    let fixture_lines = vec![
        r#"{"bobine":1,"event":"run_begin","version":"1.0.0","total":14,"user":"fanta","repo":"/home/fanta/Bobine","log":"/var/log/bobine.log","mode":"kiosk"}"#,
        "Bobine — Déploiement de la solution sur mini PC",
        r#"{"bobine":1,"event":"step","status":"start","step":1,"total":14,"pct":0,"slug":"preflight","title":"Vérification des prérequis système"}"#,
        "[INFO] Vérification Debian 13 Trixie... OK",
        r#"{"bobine":1,"event":"step","status":"ok","step":1,"total":14,"pct":7,"slug":"preflight","title":"Vérification des prérequis système"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":2,"total":14,"pct":7,"slug":"repositories","title":"Configuration des dépôts APT et firmware"}"#,
        "[INFO] Activation des dépôts non-free-firmware...",
        r#"{"bobine":1,"event":"step","status":"ok","step":2,"total":14,"pct":14,"slug":"repositories","title":"Configuration des dépôts APT et firmware"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":3,"total":14,"pct":14,"slug":"packages","title":"Installation des paquets système de base"}"#,
        "[INFO] Mise à jour des paquets...",
        r#"{"bobine":1,"event":"step","status":"ok","step":3,"total":14,"pct":25,"slug":"packages","title":"Installation des paquets système de base"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":4,"total":14,"pct":25,"slug":"gpu_codecs","title":"Détection GPU et pilotes multimédias VA-API"}"#,
        "[INFO] GPU Intel/AMD détecté. Configuration des pilotes VA-API matériels...",
        r#"{"bobine":1,"event":"step","status":"ok","step":4,"total":14,"pct":35,"slug":"gpu_codecs","title":"Détection GPU et pilotes multimédias VA-API"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":5,"total":14,"pct":35,"slug":"python_env","title":"Création de l'environnement virtuel Python"}"#,
        "[INFO] Initialisation du virtualenv et des dépendances backend...",
        r#"{"bobine":1,"event":"step","status":"ok","step":5,"total":14,"pct":50,"slug":"python_env","title":"Création de l'environnement virtuel Python"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":6,"total":14,"pct":50,"slug":"backend_db","title":"Initialisation de la base SQLite et migrations"}"#,
        "[INFO] Exécution des migrations de schéma...",
        r#"{"bobine":1,"event":"step","status":"ok","step":6,"total":14,"pct":65,"slug":"backend_db","title":"Initialisation de la base SQLite et migrations"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":7,"total":14,"pct":65,"slug":"frontend_build","title":"Déploiement des assets web Next.js"}"#,
        "[INFO] Déploiement du frontend de commande...",
        r#"{"bobine":1,"event":"step","status":"ok","step":7,"total":14,"pct":80,"slug":"frontend_build","title":"Déploiement des assets web Next.js"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":8,"total":14,"pct":80,"slug":"services","title":"Enregistrement et démarrage des services systemd"}"#,
        "[INFO] Activation de bobine-backend, bobine-kiosk...",
        r#"{"bobine":1,"event":"step","status":"ok","step":8,"total":14,"pct":92,"slug":"services","title":"Enregistrement et démarrage des services systemd"}"#,
        r#"{"bobine":1,"event":"step","status":"start","step":9,"total":14,"pct":92,"slug":"healthcheck","title":"Contrôle d'intégrité final (/api/health)"}"#,
        "[INFO] Sonde API /api/health réussie (200 OK).",
        r#"{"bobine":1,"event":"step","status":"ok","step":9,"total":14,"pct":100,"slug":"healthcheck","title":"Contrôle d'intégrité final (/api/health)"}"#,
        r#"{"bobine":1,"event":"run_end","status":"ok","pct":100,"total":14,"healthy":true,"url":"http://bobine.local:8000","port":8000}"#,
    ];

    let mut state = ProgressState::new();

    for line in fixture_lines {
        tokio::time::sleep(Duration::from_millis(150)).await;
        match classify_line(line) {
            LineKind::Event(ref ev) => {
                state.apply(ev);
                let update = progress_to_update(&state);
                app.emit("install_progress", update).ok();
            }
            LineKind::Log => {
                app.emit("install_log", line.to_string()).ok();
            }
            LineKind::Malformed(err) => {
                app.emit("install_log", format!("[WARN] Évènement malformé : {err}")).ok();
            }
        }
    }

    Ok(())
}

#[tauri::command]
pub async fn start_installation(app: tauri::AppHandle, params: RunInstallParams) -> Result<(), String> {
    if params.mock_replay {
        return run_mock_installation(app).await;
    }

    tokio::task::spawn_blocking(move || {
        let addr = format!("{}:{}", params.host, params.port);
        let tcp = TcpStream::connect_timeout(
            &addr
                .parse()
                .map_err(|e| format!("Adresse hôte invalide '{addr}' : {e}"))?,
            Duration::from_secs(5),
        )
        .map_err(|e| format!("Impossible de joindre l'hôte {addr} : {e}"))?;

        let mut sess = Session::new().map_err(|e| format!("Erreur session SSH : {e}"))?;
        sess.set_tcp_stream(tcp);
        sess.handshake().map_err(|e| format!("Échec handshake SSH : {e}"))?;

        if let Some(pwd) = &params.password {
            sess.userauth_password(&params.username, pwd)
                .map_err(|e| format!("Échec d'authentification SSH : {e}"))?;
        } else {
            sess.userauth_agent(&params.username)
                .map_err(|e| format!("Échec d'authentification agent SSH : {e}"))?;
        }

        let script = params
            .script_path
            .unwrap_or_else(|| format!("/home/{}/Bobine/install.sh", params.username));

        let elevation = if params.elevation_strategy == "su_as_user" {
            Elevation::SuRoot {
                as_user: params.username.clone(),
            }
        } else {
            Elevation::Sudo
        };

        let opts = CoreOptions {
            no_kiosk: params.no_kiosk,
            skip_packages: params.skip_packages,
            progress_json: true,
            ..Default::default()
        };

        let cmd = build_remote_command(&script, &opts, &elevation);
        app.emit("install_log", format!("> Exécution distante : {cmd}")).ok();

        let mut channel = sess
            .channel_session()
            .map_err(|e| format!("Erreur allocation canal SSH : {e}"))?;
        channel.request_pty("xterm", None, None).ok();
        channel
            .exec(&cmd)
            .map_err(|e| format!("Erreur lancement de la commande : {e}"))?;

        let mut state = ProgressState::new();
        let reader = BufReader::new(channel.stream(0));

        for line in reader.lines().map_while(Result::ok) {
            match classify_line(&line) {
                LineKind::Event(ref ev) => {
                    state.apply(ev);
                    let update = progress_to_update(&state);
                    app.emit("install_progress", update).ok();
                }
                LineKind::Log => {
                    app.emit("install_log", line).ok();
                }
                LineKind::Malformed(err) => {
                    app.emit("install_log", format!("[ATTENTION] Évènement malformé : {err}")).ok();
                }
            }
        }

        Ok(())
    })
    .await
    .map_err(|e| format!("Erreur d'exécution de tâche : {e}"))?
}
