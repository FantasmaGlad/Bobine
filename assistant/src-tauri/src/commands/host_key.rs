//! Vérification de la clé d'hôte SSH, avant tout envoi de mot de passe : sur un Wi-Fi partagé, une machine qui usurpe
//! l'adresse de la borne (ARP, mDNS) recevrait sinon le mot de passe SSH, voire celui de root.
//!
//! Fichier : `~/.ssh/known_hosts` (ou `BOBINE_SSH_KNOWN_HOSTS`), au format d'OpenSSH, lu entrées hachées comprises.
//! Une clé connue passe ; une clé inconnue n'est enregistrée qu'après que l'utilisateur a confirmé son empreinte
//! (interface : question, ligne de commande : `--trust-host-key`) ; une clé qui a changé est toujours refusée.

use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

use base64::engine::general_purpose::{STANDARD, STANDARD_NO_PAD};
use base64::Engine;
use serde::Serialize;
use ssh2::{CheckResult, HashType, HostKeyType, KnownHostFileKind, Session};

use crate::error::AssistantError;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct HostKeyInfo {
    pub host: String,
    pub port: u16,
    /// Empreinte au format d'OpenSSH (`SHA256:…`), comparable à `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.
    pub fingerprint: String,
    pub key_type: String,
    /// `known`, `unknown` ou `changed`.
    pub status: String,
    pub known_hosts: String,
}

fn known_hosts_path() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("BOBINE_SSH_KNOWN_HOSTS") {
        return Ok(PathBuf::from(path));
    }
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(|home| PathBuf::from(home).join(".ssh").join("known_hosts"))
        .ok_or_else(|| "Dossier personnel introuvable : définissez BOBINE_SSH_KNOWN_HOSTS.".to_string())
}

fn key_type_name(kind: HostKeyType) -> Option<&'static str> {
    match kind {
        HostKeyType::Rsa => Some("ssh-rsa"),
        HostKeyType::Dss => Some("ssh-dss"),
        HostKeyType::Ecdsa256 => Some("ecdsa-sha2-nistp256"),
        HostKeyType::Ecdsa384 => Some("ecdsa-sha2-nistp384"),
        HostKeyType::Ecdsa521 => Some("ecdsa-sha2-nistp521"),
        HostKeyType::Ed25519 => Some("ssh-ed25519"),
        HostKeyType::Unknown => None,
    }
}

/// Nom de l'entrée `known_hosts` : `hôte`, ou `[hôte]:port` hors du port 22 (convention d'OpenSSH).
fn entry_name(host: &str, port: u16) -> String {
    if port == 22 {
        host.to_string()
    } else {
        format!("[{host}]:{port}")
    }
}

/// Compare la clé présentée par la session (négociée, non authentifiée) au fichier `known_hosts`.
pub(crate) fn check(sess: &Session, host: &str, port: u16) -> Result<HostKeyInfo, String> {
    let (key, kind) = sess.host_key().ok_or_else(|| format!("{host}:{port} n'a présenté aucune clé d'hôte SSH."))?;
    let hash = sess
        .host_key_hash(HashType::Sha256)
        .ok_or_else(|| "Empreinte de la clé d'hôte indisponible.".to_string())?;
    let path = known_hosts_path()?;
    let mut known = sess.known_hosts().map_err(|e| format!("Lecture des clés d'hôte connues impossible : {e}"))?;
    if path.exists() {
        known
            .read_file(&path, KnownHostFileKind::OpenSSH)
            .map_err(|e| format!("Lecture de {} impossible : {e}", path.display()))?;
    }
    let status = match known.check_port(host, port, key) {
        CheckResult::Match => "known",
        CheckResult::Mismatch => "changed",
        CheckResult::NotFound => "unknown",
        CheckResult::Failure => return Err(format!("Vérification de la clé d'hôte de {host}:{port} impossible.")),
    };
    Ok(HostKeyInfo {
        host: host.to_string(),
        port,
        fingerprint: format!("SHA256:{}", STANDARD_NO_PAD.encode(hash)),
        key_type: key_type_name(kind).unwrap_or("inconnu").to_string(),
        status: status.to_string(),
        known_hosts: path.display().to_string(),
    })
}

/// Refuse une session dont la clé d'hôte n'est pas déjà connue ; appelé avant toute authentification.
pub(crate) fn require_known(sess: &Session, host: &str, port: u16) -> Result<(), AssistantError> {
    let info = check(sess, host, port).map_err(AssistantError::Failed)?;
    match info.status.as_str() {
        "known" => Ok(()),
        "changed" => Err(AssistantError::Refused(changed_message(&info))),
        _ => Err(AssistantError::Refused(format!(
            "Machine inconnue : {host}:{port} présente la clé {} {}. Vérifiez cette empreinte sur la borne \
             (ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub) puis faites-lui confiance : bouton de l'assistant, ou \
             --trust-host-key {} en ligne de commande.",
            info.key_type, info.fingerprint, info.fingerprint
        ))),
    }
}

fn changed_message(info: &HostKeyInfo) -> String {
    format!(
        "La clé d'hôte de {}:{} a changé (empreinte actuelle {}) : connexion refusée, une autre machine peut se faire \
         passer pour la borne. Si la borne a été réinstallée, retirez son ancienne entrée de {} (ssh-keygen -R {}) puis \
         recommencez.",
        info.host, info.port, info.fingerprint, info.known_hosts, entry_name(&info.host, info.port)
    )
}

/// Empreinte et statut de la clé d'hôte, sans s'authentifier.
pub fn host_key(host: &str, port: u16) -> Result<HostKeyInfo, AssistantError> {
    let sess = super::connection::connect(host, port).map_err(AssistantError::Unreachable)?;
    check(&sess, host.trim(), port).map_err(AssistantError::Failed)
}

/// Enregistre la clé d'hôte si son empreinte est celle que l'utilisateur a confirmée ; une clé changée n'est jamais
/// remplacée.
pub fn trust_host_key(host: &str, port: u16, fingerprint: &str) -> Result<HostKeyInfo, AssistantError> {
    let host = host.trim();
    let sess = super::connection::connect(host, port).map_err(AssistantError::Unreachable)?;
    let info = check(&sess, host, port).map_err(AssistantError::Failed)?;
    if info.fingerprint != fingerprint.trim() {
        return Err(AssistantError::Refused(format!(
            "{host}:{port} présente l'empreinte {} et non {} : rien n'est enregistré.",
            info.fingerprint,
            fingerprint.trim()
        )));
    }
    match info.status.as_str() {
        "known" => Ok(info),
        "changed" => Err(AssistantError::Refused(changed_message(&info))),
        _ => {
            let (key, kind) = sess.host_key().ok_or_else(|| AssistantError::Failed("Clé d'hôte absente.".to_string()))?;
            let key_type = key_type_name(kind)
                .ok_or_else(|| AssistantError::Failed("Type de clé d'hôte inconnu : enregistrement refusé.".to_string()))?;
            let path = PathBuf::from(&info.known_hosts);
            append(&path, &format!("{} {} {}\n", entry_name(host, port), key_type, STANDARD.encode(key)))
                .map_err(AssistantError::Failed)?;
            Ok(HostKeyInfo { status: "known".to_string(), ..info })
        }
    }
}

fn append(path: &std::path::Path, line: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Création de {} impossible : {e}", parent.display()))?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| format!("Ouverture de {} impossible : {e}", path.display()))?;
    file.write_all(line.as_bytes()).map_err(|e| format!("Écriture dans {} impossible : {e}", path.display()))
}

#[tauri::command]
pub async fn ssh_host_key(host: String, port: u16) -> Result<HostKeyInfo, String> {
    tokio::task::spawn_blocking(move || host_key(&host, port).map_err(String::from))
        .await
        .map_err(|e| format!("Erreur de tâche asynchrone : {e}"))?
}

#[tauri::command]
pub async fn trust_ssh_host_key(host: String, port: u16, fingerprint: String) -> Result<HostKeyInfo, String> {
    tokio::task::spawn_blocking(move || trust_host_key(&host, port, &fingerprint).map_err(String::from))
        .await
        .map_err(|e| format!("Erreur de tâche asynchrone : {e}"))?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn entry_names_follow_openssh() {
        assert_eq!(entry_name("192.168.1.20", 22), "192.168.1.20");
        assert_eq!(entry_name("bobine.local", 2222), "[bobine.local]:2222");
    }

    /// Serveur SSH de la machine de test (OpenSSH local), comme les tests de `ssh_auth.rs` : ignoré sans lui.
    #[test]
    #[ignore]
    fn unknown_key_is_refused_then_trusted_only_with_its_fingerprint() {
        let dir = std::env::temp_dir().join(format!("bobine-known-hosts-{}", std::process::id()));
        std::env::set_var("BOBINE_SSH_KNOWN_HOSTS", dir.join("known_hosts"));
        let info = host_key("127.0.0.1", 22).unwrap();
        assert_eq!(info.status, "unknown");
        assert!(trust_host_key("127.0.0.1", 22, "SHA256:faux").is_err());
        assert_eq!(trust_host_key("127.0.0.1", 22, &info.fingerprint).unwrap().status, "known");
        assert_eq!(host_key("127.0.0.1", 22).unwrap().status, "known");
        let _ = std::fs::remove_dir_all(dir);
    }
}
