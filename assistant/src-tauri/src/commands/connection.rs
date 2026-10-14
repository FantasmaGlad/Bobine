use std::io::Read;
use std::net::{SocketAddr, TcpStream, ToSocketAddrs};
use std::time::Duration;
use serde::{Deserialize, Serialize};
use ssh2::Session;

use bobine_installer_core::privilege::{decide, elevation_for, PrivilegeDecision, SudoProbe};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SshCredentials {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: Option<String>,
    /// Chemin local d'une clé privée SSH importée explicitement (bouton
    /// "Importer une clé SSH") — prioritaire sur le mot de passe et le
    /// repli automatique sur ~/.ssh/ (réf. mission "clé SSH locale").
    #[serde(default)]
    pub key_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemInspection {
    pub host: String,
    pub os_name: String,
    pub is_debian: bool,
    pub is_debian_13: bool,
    pub arch: String,
    pub is_amd64: bool,
    pub sudo_installed: bool,
    pub user_is_sudoer: bool,
    pub privilege_decision: String,
    pub needs_root_password: bool,
    pub cpu_model: String,
    pub memory_total_mb: u64,
    pub disk_free_gb: u64,
    pub gpu_info: String,
}

/// Ouvre une session SSH authentifiée vers `host:port`.
///
/// `host` peut être une IP **ou un nom** (`bobine.local`, `mini-pc`) : l'ancien
/// code faisait `format!("{host}:{port}").parse::<SocketAddr>()`, qui n'accepte
/// QUE des adresses IP littérales — saisir `bobine.local` échouait avec « Adresse
/// hôte invalide ». La résolution passe désormais par le résolveur système
/// (DNS, mDNS, hosts), avec préférence pour IPv4 (le scan n'énumère que de
/// l'IPv4 et les bornes n'annoncent pas toujours d'IPv6 joignable).
///
/// Les erreurs de connexion sont traduites en cause probable + action, au lieu
/// du texte brut de l'OS.
pub(crate) fn open_ssh_session(
    host: &str,
    port: u16,
    username: &str,
    password: Option<&str>,
    key_path: Option<&str>,
) -> Result<Session, String> {
    let host = host.trim();
    if host.is_empty() {
        return Err("Adresse de la borne manquante : sélectionnez-la dans le scan ou saisissez son IP.".to_string());
    }
    let mut addrs: Vec<SocketAddr> = (host, port)
        .to_socket_addrs()
        .map_err(|e| {
            format!("Nom ou adresse « {host} » introuvable ({e}). Essayez l'adresse IP de la borne (visible dans l'interface du routeur).")
        })?
        .collect();
    addrs.sort_by_key(|a| a.is_ipv6()); // IPv4 d'abord
    if addrs.is_empty() {
        return Err(format!("Aucune adresse trouvée pour « {host} »."));
    }

    let mut last_error = String::new();
    let mut tcp = None;
    for addr in &addrs {
        match TcpStream::connect_timeout(addr, Duration::from_secs(8)) {
            Ok(stream) => {
                tcp = Some(stream);
                break;
            }
            Err(e) => last_error = describe_connect_error(host, port, &e),
        }
    }
    let tcp = tcp.ok_or(last_error)?;
    tcp.set_nodelay(true).ok();

    let mut sess = Session::new().map_err(|e| format!("Erreur session SSH : {e}"))?;
    sess.set_tcp_stream(tcp);
    // Borne les opérations bloquantes (handshake, authentification) : une
    // machine qui accepte la connexion TCP sans parler SSH ne doit pas figer
    // l'assistant indéfiniment.
    sess.set_timeout(30_000);
    sess.handshake().map_err(|e| {
        format!("Échec de la négociation SSH avec {host}:{port} ({e}) — ce port héberge-t-il bien un serveur SSH ?")
    })?;
    // Messages de maintien de connexion : une installation dure plusieurs
    // minutes pendant lesquelles aucun octet ne circule parfois (compilation) —
    // sans eux, une box ou un Wi-Fi qui purge les connexions inactives la
    // coupait en plein milieu.
    sess.set_keepalive(true, 15);

    super::ssh_auth::authenticate_session(&sess, username, password, key_path)?;
    Ok(sess)
}

fn describe_connect_error(host: &str, port: u16, e: &std::io::Error) -> String {
    use std::io::ErrorKind::*;
    match e.kind() {
        ConnectionRefused => format!(
            "Connexion refusée par {host}:{port} : la machine est joignable mais SSH n'y est pas actif. \
             Sur la borne : « sudo apt install openssh-server » puis « sudo systemctl enable --now ssh »."
        ),
        TimedOut | WouldBlock => format!(
            "Délai dépassé vers {host}:{port} : machine éteinte, adresse erronée, autre réseau, ou isolation des clients \
             activée sur le Wi-Fi (réglage « isolation AP » / réseau invité du routeur)."
        ),
        _ => format!("Impossible de joindre {host}:{port} : {e}"),
    }
}

fn run_remote_exec(sess: &Session, cmd: &str) -> Result<String, String> {
    let mut channel = sess
        .channel_session()
        .map_err(|e| format!("Erreur création canal SSH : {e}"))?;
    channel
        .exec(cmd)
        .map_err(|e| format!("Erreur exécution commande '{cmd}' : {e}"))?;
    let mut output = String::new();
    channel
        .read_to_string(&mut output)
        .map_err(|e| format!("Erreur lecture sortie : {e}"))?;
    channel.wait_close().ok();
    Ok(output.trim().to_string())
}

#[tauri::command]
pub async fn test_ssh_connection(creds: SshCredentials) -> Result<SystemInspection, String> {
    tokio::task::spawn_blocking(move || {
        let sess = open_ssh_session(
            &creds.host,
            creds.port,
            &creds.username,
            creds.password.as_deref(),
            creds.key_path.as_deref(),
        )?;

        // 1. Détection OS
        let os_release = run_remote_exec(&sess, "cat /etc/os-release 2>/dev/null || true")?;
        let is_debian = os_release.to_lowercase().contains("id=debian")
            || os_release.to_lowercase().contains("debian");
        let is_debian_13 = os_release.contains("VERSION_ID=\"13\"") || os_release.contains("trixie");
        let os_pretty = os_release
            .lines()
            .find(|l| l.starts_with("PRETTY_NAME="))
            .map(|l| l.trim_start_matches("PRETTY_NAME=").trim_matches('"').to_string())
            .unwrap_or_else(|| "Système Linux inconnu".to_string());

        // 2. Architecture CPU
        let arch = run_remote_exec(&sess, "uname -m")?;
        let is_amd64 = arch.contains("x86_64") || arch.contains("amd64");

        // 3. Sondes sudo / su
        let sudo_check = run_remote_exec(&sess, "command -v sudo >/dev/null 2>&1 && echo yes || echo no")?;
        let sudo_installed = sudo_check == "yes";

        let sudoer_check = if sudo_installed {
            run_remote_exec(&sess, "sudo -n true >/dev/null 2>&1 && echo yes || echo no")?
        } else {
            "no".to_string()
        };
        let user_is_sudoer = sudoer_check == "yes";

        let probe = SudoProbe {
            sudo_installed,
            user_is_sudoer,
        };
        let decision = decide(&probe);
        let _elevation = elevation_for(decision, &creds.username);
        let needs_root_password = decision == PrivilegeDecision::BootstrapSuAsUser;

        // 4. Métriques matérielles
        let cpu_info = run_remote_exec(&sess, "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs || uname -p")
            .unwrap_or_else(|_| "Processeur x86-64".to_string());

        let mem_total_kb = run_remote_exec(&sess, "grep MemTotal /proc/meminfo | awk '{print $2}'")
            .unwrap_or_default()
            .parse::<u64>()
            .unwrap_or(4096000);
        let memory_total_mb = mem_total_kb / 1024;

        let disk_free_kb = run_remote_exec(&sess, "df -k / | tail -1 | awk '{print $4}'")
            .unwrap_or_default()
            .parse::<u64>()
            .unwrap_or(20000000);
        let disk_free_gb = disk_free_kb / (1024 * 1024);

        let gpu_info = run_remote_exec(&sess, "lspci 2>/dev/null | grep -E 'VGA|3D|Display' | cut -d: -f3 | xargs || true")
            .unwrap_or_else(|_| "iGPU / Accélération graphique standard".to_string());

        Ok(SystemInspection {
            host: creds.host,
            os_name: os_pretty,
            is_debian,
            is_debian_13,
            arch,
            is_amd64,
            sudo_installed,
            user_is_sudoer,
            privilege_decision: match decision {
                PrivilegeDecision::UseSudo => "sudo".to_string(),
                PrivilegeDecision::BootstrapSuAsUser => "su_as_user".to_string(),
            },
            needs_root_password,
            cpu_model: if cpu_info.is_empty() { "AMD/Intel x86-64".to_string() } else { cpu_info },
            memory_total_mb,
            disk_free_gb,
            gpu_info: if gpu_info.is_empty() { "Graphismes intégrés".to_string() } else { gpu_info },
        })
    })
    .await
    .map_err(|e| format!("Erreur de tâche asynchrone : {e}"))?
}
