//! Commande `bobine-assistant` : tout ce que fait l'interface, en ligne de commande, sur les mêmes fonctions
//! (`discovery::scan`, `connection::inspect`, `install::run_installation`). Même contrat que la commande `bobine` :
//! sortie lisible ou `--json` sur stdout, messages sur stderr, codes de sortie 0 succès, 1 échec, 2 usage,
//! 3 cible injoignable, 4 authentification refusée.
//!
//! Les mots de passe ne passent jamais en argument (visibles dans la liste des processus) : variable d'environnement
//! (`BOBINE_SSH_PASSWORD`, `BOBINE_ROOT_PASSWORD`) ou une ligne de l'entrée standard (`--password-stdin`,
//! `--root-password-stdin`, dans cet ordre).

use std::io::{BufRead, Write};

use clap::{Parser, Subcommand, ValueEnum};
use serde_json::{json, Value};

use crate::commands::connection::{inspect, SshCredentials};
use crate::commands::discovery::scan;
use crate::commands::host_key::{host_key, trust_host_key};
use crate::commands::install::{run_installation, RunInstallParams};
use crate::error::AssistantError;
use crate::events::Events;

/// `println!` qui ne panique pas quand la sortie est fermée (`bobine-assistant scan | head`).
macro_rules! out {
    ($($arg:tt)*) => {{
        let _ = writeln!(std::io::stdout().lock(), $($arg)*);
    }};
}

pub const EXIT_OK: i32 = 0;
pub const EXIT_ERROR: i32 = 1;
pub const EXIT_USAGE: i32 = 2;
pub const EXIT_UNREACHABLE: i32 = 3;
pub const EXIT_REFUSED: i32 = 4;

/// Sous-commandes reconnues : leur présence en argument lance la ligne de commande au lieu de la fenêtre.
pub const COMMANDS: [&str; 6] = ["scan", "host-key", "inspect", "install", "update", "version"];

#[derive(Parser, Debug)]
#[command(name = "bobine-assistant", about = "Installer Bobine sur un mini PC du réseau, sans interface.", version = env!("BOBINE_VERSION"))]
struct Cli {
    /// Sortie JSON sur stdout (JSON lignes pendant une installation).
    #[arg(long, global = true)]
    json: bool,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Chercher les machines du réseau local (ou d'un réseau donné).
    Scan {
        /// Adresse ou réseau à sonder (192.168.2.10 ou 192.168.2.0/24) ; défaut : réseaux des interfaces actives.
        #[arg(long)]
        subnet: Option<String>,
    },
    /// Empreinte et statut de la clé d'hôte SSH de la cible (connue, inconnue, changée), sans s'authentifier.
    HostKey {
        /// Adresse IP ou nom de la cible.
        #[arg(long)]
        host: String,
        #[arg(long, default_value_t = 22)]
        port: u16,
    },
    /// Se connecter en SSH et auditer la cible (système, architecture, élévation, matériel).
    Inspect {
        #[command(flatten)]
        target: Target,
    },
    /// Installer Bobine sur la cible (exige --yes).
    Install {
        #[command(flatten)]
        target: Target,
        /// Canal installé sur la cible.
        #[arg(long, value_enum, default_value_t = Channel::Stable)]
        channel: Channel,
        /// Élévation : auto (déterminée par l'audit, comme l'interface), sudo, ou su (mot de passe root requis).
        #[arg(long, value_enum, default_value_t = Elevation::Auto)]
        elevation: Elevation,
        /// Sans l'écran plein écran (kiosque) sur la cible.
        #[arg(long)]
        no_kiosk: bool,
        /// Sans installer les paquets système (déjà présents).
        #[arg(long)]
        skip_packages: bool,
        /// Script d'installation déjà présent sur la cible, au lieu du script embarqué.
        #[arg(long, value_name = "CHEMIN")]
        script: Option<String>,
        /// Rejoue une installation enregistrée sans toucher la cible (démonstration, essais).
        #[arg(long)]
        simulate: bool,
        /// Lire le mot de passe root sur l'entrée standard (après celui de --password-stdin).
        #[arg(long)]
        root_password_stdin: bool,
        /// Confirmer l'installation (la cible est modifiée).
        #[arg(long)]
        yes: bool,
    },
    /// Mise à jour de l'assistant lui-même (même vérification de signature que l'interface).
    Update {
        #[command(subcommand)]
        action: UpdateAction,
    },
    /// Version de l'assistant.
    Version,
}

#[derive(Subcommand, Debug)]
enum UpdateAction {
    /// Chercher une version plus récente sur le canal de ce build.
    Check,
    /// Télécharger, vérifier et installer la version plus récente (exige --yes) ; relancer ensuite l'assistant.
    Apply {
        #[arg(long)]
        yes: bool,
    },
}

#[derive(clap::Args, Debug)]
struct Target {
    /// Adresse IP ou nom de la cible (bobine.local, mini-pc...).
    #[arg(long)]
    host: String,
    #[arg(long, default_value_t = 22)]
    port: u16,
    /// Utilisateur SSH (défaut : variable USER).
    #[arg(long)]
    user: Option<String>,
    /// Clé privée SSH (sinon : agent SSH, puis clés usuelles de ~/.ssh).
    #[arg(long, value_name = "FICHIER")]
    key: Option<String>,
    /// Lire le mot de passe SSH sur l'entrée standard (sinon BOBINE_SSH_PASSWORD).
    #[arg(long)]
    password_stdin: bool,
    /// Faire confiance à une cible inconnue dont la clé a cette empreinte (SHA256:…, donnée par `host-key`) ;
    /// une clé qui a changé reste refusée.
    #[arg(long, value_name = "EMPREINTE")]
    trust_host_key: Option<String>,
}

#[derive(ValueEnum, Clone, Copy, Debug)]
enum Channel {
    Stable,
    Beta,
    Canary,
}

#[derive(ValueEnum, Clone, Copy, Debug, PartialEq, Eq)]
enum Elevation {
    Auto,
    Sudo,
    Su,
}

/// Vrai quand les arguments demandent la ligne de commande : une sous-commande, ou `--help`/`--version` seuls.
pub fn is_invocation(args: &[String]) -> bool {
    args.iter().skip(1).any(|a| COMMANDS.contains(&a.as_str()) || matches!(a.as_str(), "-h" | "--help" | "-V" | "--version"))
}

/// Événements de l'installation et du scan sur la console : JSON lignes sur stdout avec `--json`, sinon journal et
/// progression lisibles sur stderr.
struct Console {
    json: bool,
}

impl Events for Console {
    fn send(&self, name: &str, payload: Value) {
        if self.json {
            if name != "scan_device" && name != "scan_progress" {
                out!("{}", json!({ "event": name, "data": payload }));
            }
            return;
        }
        match name {
            "install_log" => eprintln!("{}", printable(payload.as_str().unwrap_or_default())),
            "install_progress" => eprintln!(
                "[{:>3} %] {}",
                payload["pct"].as_u64().unwrap_or(0),
                payload["step_title"].as_str().unwrap_or_default()
            ),
            "assistant-update-progress" => eprint!(
                "\rTéléchargement : {} Mo{}",
                payload["downloaded"].as_u64().unwrap_or(0) / 1_048_576,
                payload["total"].as_u64().map(|t| format!(" / {} Mo", t / 1_048_576)).unwrap_or_default()
            ),
            "scan_progress" => eprint!(
                "\rSondage : {}/{} adresses, {} trouvée(s)",
                payload["done"].as_u64().unwrap_or(0),
                payload["total"].as_u64().unwrap_or(0),
                payload["found"].as_u64().unwrap_or(0)
            ),
            _ => {}
        }
    }
}

pub fn main(args: Vec<String>) -> i32 {
    attach_console();
    let cli = match Cli::try_parse_from(&args) {
        Ok(cli) => cli,
        Err(e) => {
            let code = if e.use_stderr() { EXIT_USAGE } else { EXIT_OK };
            let _ = e.print();
            return code;
        }
    };
    let json = cli.json;
    match run(cli) {
        Ok(()) => EXIT_OK,
        Err(error) => {
            let code = match error {
                AssistantError::Unreachable(_) => EXIT_UNREACHABLE,
                AssistantError::Refused(_) => EXIT_REFUSED,
                AssistantError::Failed(_) => EXIT_ERROR,
                AssistantError::Usage(_) => EXIT_USAGE,
            };
            if json {
                out!("{}", json!({ "event": "error", "data": { "code": code, "message": error.message() } }));
            }
            eprintln!("bobine-assistant : {error}");
            code
        }
    }
}

fn run(cli: Cli) -> Result<(), AssistantError> {
    let console = Console { json: cli.json };
    match cli.command {
        Command::Version => {
            let (version, commit) = (env!("BOBINE_VERSION"), env!("BOBINE_COMMIT"));
            if cli.json {
                out!("{}", json!({ "version": version, "commit": commit }));
            } else {
                out!("bobine-assistant {version} ({commit})");
            }
            Ok(())
        }
        Command::Scan { subnet } => {
            let runtime = tokio::runtime::Runtime::new().map_err(|e| AssistantError::Failed(e.to_string()))?;
            let devices = runtime.block_on(scan(&console, subnet))?;
            if cli.json {
                out!("{}", serde_json::to_string_pretty(&devices).unwrap_or_default());
            } else {
                eprintln!();
                for device in &devices {
                    let ports: Vec<String> = device.open_ports.iter().map(u16::to_string).collect();
                    out!(
                        "{:<16} {:<28} {}{}{}",
                        device.ip,
                        printable(device.hostname.as_deref().unwrap_or("-")),
                        if device.bobine_open { "Bobine " } else { "" },
                        if device.ssh_open { "SSH " } else { "" },
                        if ports.is_empty() { String::new() } else { format!("(ports {})", ports.join(", ")) },
                    );
                }
                eprintln!("{} appareil(s).", devices.len());
            }
            Ok(())
        }
        Command::Update { action } => update(action, &console, cli.json),
        Command::HostKey { host, port } => {
            let info = host_key(&host, port)?;
            if cli.json {
                out!("{}", serde_json::to_string_pretty(&info).unwrap_or_default());
            } else {
                let status = match info.status.as_str() {
                    "known" => "connue",
                    "changed" => "CHANGÉE : connexion refusée",
                    _ => "inconnue",
                };
                out!("{} {}  ({status}, {})", info.key_type, info.fingerprint, info.known_hosts);
            }
            Ok(())
        }
        Command::Inspect { target } => {
            trust(&target)?;
            let mut input = std::io::stdin().lock();
            let creds = credentials(&target, &mut input)?;
            let report = inspect(creds)?;
            if cli.json {
                out!("{}", serde_json::to_string_pretty(&report).unwrap_or_default());
            } else {
                out!("Système      {}", report.os_name);
                out!("Architecture {}", report.arch);
                out!("Processeur   {}", report.cpu_model);
                out!("Mémoire      {} Mo, disque libre {} Go", report.memory_total_mb, report.disk_free_gb);
                out!("Graphismes   {}", report.gpu_info);
                out!(
                    "Élévation    {}",
                    if report.needs_root_password { "su (mot de passe root requis)" } else { "sudo" }
                );
            }
            Ok(())
        }
        Command::Install { target, channel, elevation, no_kiosk, skip_packages, script, simulate, root_password_stdin, yes } => {
            if !yes {
                return Err(AssistantError::Usage(
                    "L'installation modifie la cible : relancez avec --yes pour confirmer.".to_string(),
                ));
            }
            trust(&target)?;
            let mut input = std::io::stdin().lock();
            let creds = credentials(&target, &mut input)?;
            let root_password = if root_password_stdin {
                Some(read_line(&mut input, "mot de passe root")?)
            } else {
                std::env::var("BOBINE_ROOT_PASSWORD").ok().filter(|p| !p.is_empty())
            };
            let elevation_strategy = match elevation {
                Elevation::Sudo => "sudo".to_string(),
                Elevation::Su => "su_as_user".to_string(),
                // Comme l'interface : l'audit de la cible tranche entre sudo et su.
                Elevation::Auto if simulate => "sudo".to_string(),
                Elevation::Auto => inspect(creds.clone())?.privilege_decision,
            };
            let params = RunInstallParams {
                host: creds.host,
                port: creds.port,
                username: creds.username,
                password: creds.password,
                key_path: creds.key_path,
                root_password,
                elevation_strategy,
                script_path: script,
                no_kiosk,
                skip_packages,
                mock_replay: simulate,
                channel: format!("{channel:?}").to_lowercase(),
            };
            run_installation(&console, params)?;
            if cli.json {
                out!("{}", json!({ "event": "done", "data": { "ok": true } }));
            } else {
                eprintln!("Installation terminée.");
            }
            Ok(())
        }
    }
}

/// Le greffon de mise à jour exige une application Tauri : construite ici sans fenêtre, jamais lancée. Il lui faut une
/// session graphique sous Linux (l'assistant est une application de bureau).
fn update(action: UpdateAction, console: &Console, json: bool) -> Result<(), AssistantError> {
    use tauri_plugin_updater::UpdaterExt;

    if let UpdateAction::Apply { yes: false } = action {
        return Err(AssistantError::Usage("La mise à jour remplace l'assistant : relancez avec --yes pour confirmer.".to_string()));
    }
    let mut context = crate::context();
    context.config_mut().app.windows.clear();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .build(context)
        .map_err(|e| AssistantError::Failed(format!("Initialisation de l'assistant impossible (session graphique requise) : {e}")))?;
    let current = app.package_info().version.to_string();
    let updater = app.updater().map_err(|e| AssistantError::Failed(e.to_string()))?;
    tauri::async_runtime::block_on(async {
        let update = updater.check().await.map_err(|e| match e {
            tauri_plugin_updater::Error::TargetNotFound(_) | tauri_plugin_updater::Error::TargetsNotFound(_) => {
                AssistantError::Failed(crate::commands::update::describe(e))
            }
            other => AssistantError::Unreachable(other.to_string()),
        })?;
        let Some(update) = update else {
            if json {
                out!("{}", json!({ "available": false, "current": current }));
            } else {
                out!("Bobine Assistant {current} est à jour.");
            }
            return Ok(());
        };
        if let UpdateAction::Check = action {
            if json {
                out!("{}", json!({ "available": true, "current": current, "version": update.version }));
            } else {
                out!("Bobine Assistant {} est disponible (installée : {current}).", update.version);
            }
            return Ok(());
        }
        let mut downloaded = 0u64;
        update
            .download_and_install(
                |chunk, total| {
                    downloaded += chunk as u64;
                    console.send("assistant-update-progress", json!({ "downloaded": downloaded, "total": total }));
                },
                || {},
            )
            .await
            .map_err(|e| AssistantError::Failed(e.to_string()))?;
        if json {
            out!("{}", json!({ "event": "done", "data": { "ok": true, "version": update.version } }));
        } else {
            eprintln!("Bobine Assistant {} installé : relancez-le.", update.version);
        }
        Ok(())
    })
}

/// `--trust-host-key` : enregistre la clé de la cible si son empreinte est celle donnée.
fn trust(target: &Target) -> Result<(), AssistantError> {
    if let Some(fingerprint) = target.trust_host_key.as_deref() {
        trust_host_key(&target.host, target.port, fingerprint)?;
    }
    Ok(())
}

fn credentials(target: &Target, input: &mut impl BufRead) -> Result<SshCredentials, AssistantError> {
    let username = target
        .user
        .clone()
        .or_else(|| std::env::var("USER").ok())
        .or_else(|| std::env::var("USERNAME").ok())
        .filter(|u| !u.trim().is_empty())
        .ok_or_else(|| AssistantError::Usage("Utilisateur SSH inconnu : précisez --user.".to_string()))?;
    let password = if target.password_stdin {
        Some(read_line(input, "mot de passe SSH")?)
    } else {
        std::env::var("BOBINE_SSH_PASSWORD").ok().filter(|p| !p.is_empty())
    };
    Ok(SshCredentials { host: target.host.clone(), port: target.port, username, password, key_path: target.key.clone() })
}

/// Texte venu du réseau (nom d'hôte, journal de la cible) sans caractères de contrôle ni de direction : il ne peut ni
/// piloter le terminal (séquences ANSI, OSC) ni réordonner visuellement la ligne (U+202E...).
fn printable(text: &str) -> String {
    text.chars()
        .filter(|c| !c.is_control() && !matches!(*c, '\u{200E}' | '\u{200F}' | '\u{202A}'..='\u{202E}' | '\u{2066}'..='\u{2069}'))
        .collect()
}

fn read_line(input: &mut impl BufRead, what: &str) -> Result<String, AssistantError> {
    let mut line = String::new();
    input
        .read_line(&mut line)
        .map_err(|e| AssistantError::Failed(format!("Lecture du {what} sur l'entrée standard impossible : {e}")))?;
    let value = line.trim_end_matches(['\r', '\n']).to_string();
    if value.is_empty() {
        return Err(AssistantError::Failed(format!("Aucun {what} sur l'entrée standard.")));
    }
    Ok(value)
}

/// Sous Windows, l'exécutable de l'interface n'a pas de console : la ligne de commande se rattache à celle du terminal
/// qui l'a lancée, sinon rien ne s'afficherait.
fn attach_console() {
    #[cfg(windows)]
    unsafe {
        windows_sys::Win32::System::Console::AttachConsole(windows_sys::Win32::System::Console::ATTACH_PARENT_PROCESS);
    }
    let _ = std::io::stdout().flush();
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(list: &[&str]) -> Vec<String> {
        list.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn subcommands_and_help_start_the_command_line() {
        assert!(is_invocation(&args(&["bobine-assistant", "scan"])));
        assert!(is_invocation(&args(&["bobine-assistant", "--json", "version"])));
        assert!(is_invocation(&args(&["bobine-assistant", "--help"])));
        assert!(!is_invocation(&args(&["bobine-assistant"])));
        assert!(!is_invocation(&args(&["bobine-assistant", "-psn_0_12345"])));
    }

    #[test]
    fn usage_errors_and_missing_confirmation() {
        assert_eq!(main(args(&["bobine-assistant", "install"])), EXIT_USAGE);
        assert_eq!(main(args(&["bobine-assistant", "install", "--host", "203.0.113.10", "--channel", "nightly"])), EXIT_USAGE);
        assert_eq!(main(args(&["bobine-assistant", "install", "--host", "203.0.113.10", "--user", "admin"])), EXIT_USAGE);
        assert_eq!(main(args(&["bobine-assistant", "update", "apply"])), EXIT_USAGE);
        assert_eq!(main(args(&["bobine-assistant", "version"])), EXIT_OK);
    }

    #[test]
    fn simulated_install_runs_the_shared_installation() {
        let code = main(args(&[
            "bobine-assistant", "--json", "install", "--host", "203.0.113.10", "--user", "admin", "--simulate", "--yes",
        ]));
        assert_eq!(code, EXIT_OK);
    }

    #[test]
    fn unreachable_target_has_its_own_exit_code() {
        // Port 9 de la boucle locale : connexion refusée immédiatement, sans réseau.
        let code = main(args(&["bobine-assistant", "inspect", "--host", "127.0.0.1", "--port", "9", "--user", "admin"]));
        assert_eq!(code, EXIT_UNREACHABLE);
    }

    #[test]
    fn network_text_cannot_drive_the_terminal() {
        assert_eq!(printable("borne\u{1b}]0;titre\u{7}\u{202E}gpj.exe"), "borne]0;titregpj.exe");
        assert_eq!(printable("[INFO] Étape 3/14 terminée"), "[INFO] Étape 3/14 terminée");
    }

    #[test]
    fn passwords_are_read_line_by_line_from_stdin() {
        let mut input = std::io::Cursor::new("secret ssh\r\nsecret root\n");
        assert_eq!(read_line(&mut input, "mot de passe SSH").unwrap(), "secret ssh");
        assert_eq!(read_line(&mut input, "mot de passe root").unwrap(), "secret root");
        assert!(read_line(&mut input, "mot de passe").is_err());
    }
}
