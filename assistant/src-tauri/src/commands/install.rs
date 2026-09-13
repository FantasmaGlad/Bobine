use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::{Duration, Instant};
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
    /// Chemin local d'une clé privée SSH importée explicitement — voir
    /// `SshCredentials::key_path` (même mécanisme, relayé depuis l'étape 2
    /// du wizard jusqu'à l'installation elle-même).
    #[serde(default)]
    pub key_path: Option<String>,
    pub root_password: Option<String>,
    pub elevation_strategy: String,
    pub script_path: Option<String>,
    pub no_kiosk: bool,
    pub skip_packages: bool,
    pub mock_replay: bool,
    /// Canal de mise à jour de la cible (réf. mission "canal Stable/Bêta") —
    /// "stable" ou "beta", relayé tel quel à `install.sh --channel=<...>`.
    #[serde(default = "default_channel")]
    pub channel: String,
}

fn default_channel() -> String {
    "stable".to_string()
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

/// Écrase le contenu d'un secret (mot de passe root) avant qu'il ne sorte de
/// portée. Pas de dépendance `zeroize` dans ce crate : une écriture volatile
/// octet par octet suffit à éviter qu'il traîne lisible dans un tas libéré,
/// sans risquer d'être supprimée par l'optimiseur comme un simple `for b in
/// s.as_bytes_mut() { *b = 0 }` le pourrait. Les octets de remplacement (0)
/// restent de l'ASCII valide, donc la chaîne reste UTF-8 valide.
fn scrub_secret(s: &mut str) {
    let bytes = unsafe { s.as_bytes_mut() };
    for b in bytes {
        unsafe { std::ptr::write_volatile(b, 0u8) };
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

        super::ssh_auth::authenticate_session(
            &sess,
            &params.username,
            params.password.as_deref(),
            params.key_path.as_deref(),
        )?;

        let script = params
            .script_path
            .unwrap_or_else(|| format!("/home/{}/Bobine/install.sh", params.username));

        let needs_root_password = params.elevation_strategy == "su_as_user";
        let elevation = if needs_root_password {
            Elevation::SuRoot {
                as_user: params.username.clone(),
            }
        } else {
            Elevation::Sudo
        };

        // Le mot de passe root n'est nécessaire que pour l'option B (`su -`,
        // cf. privilege.rs::PrivilegeDecision::BootstrapSuAsUser) : c'est le
        // seul cas où la commande distante s'arrête sur une invite
        // interactive avant de continuer (voir en-tête d'orchestrate.rs).
        // On le sort de `params` une bonne fois pour n'en garder qu'une
        // seule copie en mémoire, à écraser en fin de fonction.
        let mut root_password = params.root_password;
        if needs_root_password && root_password.as_deref().is_none_or(|p| p.trim().is_empty()) {
            return Err(
                "Le mot de passe root est requis pour lancer l'installation via « su - » sur cette machine, mais aucun mot de passe n'a été fourni.".to_string(),
            );
        }

        let opts = CoreOptions {
            no_kiosk: params.no_kiosk,
            skip_packages: params.skip_packages,
            progress_json: true,
            channel: params.channel.clone(),
            ..Default::default()
        };

        let cmd = build_remote_command(&script, &opts, &elevation);
        app.emit("install_log", format!("> Exécution distante : {cmd}")).ok();

        let mut channel = sess
            .channel_session()
            .map_err(|e| format!("Erreur allocation canal SSH : {e}"))?;
        // PTY requis dans tous les cas : `su -` (et certains `sudo`) ne
        // présentent leur invite de mot de passe interactive que si un
        // terminal est alloué côté distant — sans lui, la commande resterait
        // bloquée en silence en attendant une saisie qui ne peut jamais
        // arriver sur un canal non-PTY.
        channel.request_pty("xterm", None, None).ok();
        channel
            .exec(&cmd)
            .map_err(|e| format!("Erreur lancement de la commande : {e}"))?;

        let mut state = ProgressState::new();

        // Mode non bloquant : seul moyen de borner à 20s l'attente de
        // l'invite mot de passe ci-dessous sans geler l'installation si
        // `su -` ne la présente jamais (c'était le bug d'origine : le mot de
        // passe collecté par l'IHM n'était jamais écrit sur le canal SSH et
        // l'installation restait bloquée indéfiniment, sans erreur visible).
        sess.set_blocking(false);

        let mut password_sent = !needs_root_password;
        let prompt_deadline = Instant::now() + Duration::from_secs(20);
        // Octets reçus pas encore découpés en lignes complètes.
        let mut pending: Vec<u8> = Vec::new();

        let result: Result<(), String> = loop {
            let mut chunk = [0u8; 4096];
            match channel.read(&mut chunk) {
                Ok(0) => break Ok(()), // canal fermé : la commande distante s'est terminée
                Ok(n) => {
                    pending.extend_from_slice(&chunk[..n]);

                    // L'invite de mot de passe n'est jamais suivie d'un saut
                    // de ligne (le shell distant attend la saisie) : on
                    // l'observe donc sur le buffer brut, avant le découpage
                    // en lignes ci-dessous qui ne voit que du texte déjà
                    // terminé par '\n'.
                    if !password_sent {
                        let lower = String::from_utf8_lossy(&pending).to_lowercase();
                        if lower.contains("password") || lower.contains("mot de passe") {
                            if let Some(pwd) = root_password.as_deref() {
                                let mut to_send = format!("{pwd}\n");
                                // Écriture bloquante ponctuelle : évite de
                                // traiter un simple `WouldBlock` transitoire
                                // sur ce petit envoi comme un échec réel.
                                sess.set_blocking(true);
                                let write_res = channel.write_all(to_send.as_bytes());
                                sess.set_blocking(false);
                                scrub_secret(&mut to_send);
                                if let Err(e) = write_res {
                                    break Err(format!(
                                        "Échec de transmission du mot de passe root sur le canal SSH : {e}"
                                    ));
                                }
                            }
                            password_sent = true;
                            // L'invite elle-même ne doit pas être réinterprétée
                            // comme une ligne de log/progression JSON.
                            pending.clear();
                        }
                    }

                    while let Some(pos) = pending.iter().position(|&b| b == b'\n') {
                        let raw_line: Vec<u8> = pending.drain(..=pos).collect();
                        let line = String::from_utf8_lossy(&raw_line);
                        let line = line.trim_end_matches(['\r', '\n']);
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
                                app.emit(
                                    "install_log",
                                    format!("[ATTENTION] Évènement malformé : {err}"),
                                )
                                .ok();
                            }
                        }
                    }
                }
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    if !password_sent && Instant::now() >= prompt_deadline {
                        break Err(
                            "Le mot de passe root n'a pas pu être transmis — invite de mot de passe non détectée sur la machine distante".to_string(),
                        );
                    }
                    std::thread::sleep(Duration::from_millis(80));
                }
                Err(e) => break Err(format!("Erreur de lecture du canal SSH : {e}")),
            }
        };

        // Le secret ne doit pas survivre au-delà de ce point, qu'il ait
        // servi (élévation `su -`) ou non (élévation `sudo`, échec avant
        // détection de l'invite...).
        if let Some(pwd) = root_password.as_mut() {
            scrub_secret(pwd);
        }
        drop(root_password);

        result
    })
    .await
    .map_err(|e| format!("Erreur d'exécution de tâche : {e}"))?
}
