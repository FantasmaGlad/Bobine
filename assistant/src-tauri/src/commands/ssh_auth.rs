use std::path::PathBuf;
use ssh2::{Prompt, Session};
use tauri_plugin_dialog::DialogExt;

struct SimplePasswordPrompt<'a>(&'a str);

impl<'a> ssh2::KeyboardInteractivePrompt for SimplePasswordPrompt<'a> {
    fn prompt<'b>(
        &mut self,
        _username: &str,
        _instructions: &str,
        prompts: &[Prompt<'b>],
    ) -> Vec<String> {
        prompts.iter().map(|_| self.0.to_string()).collect()
    }
}

/// Authentifie une session SSH en testant successivement :
/// 1. Clé SSH explicitement importée par l'utilisateur (bouton "Importer une
///    clé SSH", réf. mission "clé SSH locale") — prioritaire sur tout le
///    reste puisque choisie sciemment.
/// 2. Mot de passe direct (si renseigné)
/// 3. Authentification clavier-interactive / PAM (si mot de passe renseigné)
/// 4. Agent SSH local (`ssh-agent`)
/// 5. Fichiers de clés SSH courantes dans `~/.ssh/` (`id_ed25519`, `id_rsa`, `id_ecdsa`, etc.)
///
/// Si toutes les méthodes échouent, renvoie un message d'erreur clair et contextuel
/// (en particulier si le serveur distant refuse explicitement les mots de passe).
pub fn authenticate_session(
    sess: &Session,
    username: &str,
    password: Option<&str>,
    key_path: Option<&str>,
) -> Result<(), String> {
    let supported = sess.auth_methods(username).unwrap_or("");
    let password_clean = password.filter(|p| !p.trim().is_empty());

    // 0. Tenter la clé explicitement importée en premier
    if let Some(key) = key_path.filter(|k| !k.trim().is_empty()) {
        let priv_key = PathBuf::from(key);
        let pub_key = PathBuf::from(format!("{key}.pub"));
        let pub_path = if pub_key.exists() {
            Some(pub_key.as_path())
        } else {
            None
        };
        let _ = sess.userauth_pubkey_file(username, pub_path, &priv_key, None);
        if sess.authenticated() {
            return Ok(());
        }
        // Clé passphrase-protégée ou refusée par le serveur : on retente
        // avec le mot de passe fourni comme passphrase de déchiffrement,
        // avant de retomber sur le reste de la chaîne (agent, clés
        // usuelles...) plutôt que d'échouer immédiatement.
        if let Some(pwd) = password_clean {
            let _ = sess.userauth_pubkey_file(username, pub_path, &priv_key, Some(pwd));
            if sess.authenticated() {
                return Ok(());
            }
        }
    }

    // 2. Tenter le mot de passe si disponible
    if let Some(pwd) = password_clean {
        let _ = sess.userauth_password(username, pwd);
        if sess.authenticated() {
            return Ok(());
        }

        // Tenter le mode clavier interactif / PAM
        let mut prompt = SimplePasswordPrompt(pwd);
        let _ = sess.userauth_keyboard_interactive(username, &mut prompt);
        if sess.authenticated() {
            return Ok(());
        }
    }

    // 3. Tenter l'agent SSH (ssh-agent)
    let _ = sess.userauth_agent(username);
    if sess.authenticated() {
        return Ok(());
    }

    // 4. Tenter les clés SSH locales usuelles dans ~/.ssh/
    if let Ok(home) = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")) {
        let ssh_dir = PathBuf::from(home).join(".ssh");
        let key_candidates = [
            "id_ed25519",
            "id_rsa",
            "id_ecdsa",
            "deploy_key_lutecium",
            "lutecium_deploy",
            "bobineweb_deploy",
        ];

        for key_name in &key_candidates {
            let priv_key = ssh_dir.join(key_name);
            if priv_key.exists() {
                let pub_key = ssh_dir.join(format!("{key_name}.pub"));
                let pub_path = if pub_key.exists() {
                    Some(pub_key.as_path())
                } else {
                    None
                };
                let _ = sess.userauth_pubkey_file(username, pub_path, &priv_key, None);
                if sess.authenticated() {
                    return Ok(());
                }
            }
        }
    }

    if sess.authenticated() {
        return Ok(());
    }

    // Diagnostic précis et instructif
    let allows_password = supported
        .split(',')
        .any(|m| m.trim() == "password" || m.trim() == "keyboard-interactive");

    if !allows_password && !supported.is_empty() {
        Err(format!(
            "Le serveur SSH de la cible refuse les mots de passe (PasswordAuthentication désactivé dans /etc/ssh/sshd_config). Méthodes acceptées : [{supported}]. Activez 'PasswordAuthentication yes' sur la cible ou installez votre clé publique dans ~/.ssh/authorized_keys."
        ))
    } else if password_clean.is_some() {
        Err(format!(
            "Authentification refusée pour '{username}' : mot de passe incorrect ou clés locales rejetées."
        ))
    } else {
        Err(format!(
            "Aucun mot de passe fourni et aucune clé SSH locale autorisée par le serveur. Méthodes acceptées : [{supported}]."
        ))
    }
}

/// Ouvre le sélecteur de fichier natif pour importer une clé privée SSH
/// locale (bouton "Importer une clé SSH" de l'étape 2, alternative au mot
/// de passe et au repli automatique sur `~/.ssh/`) — utile pour une clé
/// stockée à un emplacement ou sous un nom non standard. `pick_file` de
/// l'API dialog est callback-based (synchrone côté thread principal) ; le
/// canal one-shot le relie proprement à cette commande async. `None` si
/// l'utilisateur ferme le sélecteur sans choisir de fichier.
#[tauri::command]
pub async fn pick_ssh_key_file(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();
    app.dialog()
        .file()
        .set_title("Sélectionner une clé privée SSH")
        .pick_file(move |file_path| {
            let _ = tx.send(file_path.map(|p| p.to_string()));
        });
    rx.await
        .map_err(|e| format!("Erreur du sélecteur de fichier : {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpStream;
    use std::time::Duration;

    /// Hôte ciblé par les tests d'intégration SSH ci-dessous. Ils ont besoin
    /// d'un vrai serveur SSH joignable (d'où le `#[ignore]` : ils ne
    /// tournent pas en CI ni par défaut en local) ; la variable d'env évite
    /// de coder l'adresse d'une machine de développement en dur dans le
    /// dépôt. Par défaut : loopback, pour un sshd local le cas échéant.
    fn test_ssh_host() -> String {
        std::env::var("BOBINE_TEST_SSH_HOST").unwrap_or_else(|_| "127.0.0.1".to_string())
    }

    #[test]
    #[ignore = "nécessite un serveur SSH accessible (voir BOBINE_TEST_SSH_HOST) en environnement de développement"]
    fn test_auth_fallback_with_password_or_key() {
        let addr = format!("{}:22", test_ssh_host());
        // Test uniquement si l'hôte est joignable
        if let Ok(tcp) = TcpStream::connect_timeout(&addr.parse().unwrap(), Duration::from_millis(500)) {
            let mut sess = Session::new().unwrap();
            sess.set_tcp_stream(tcp);
            sess.handshake().unwrap();

            // Même si on donne un mot de passe qui échoue (ou rejeté par le serveur),
            // authenticate_session doit automatiquement se replier sur l'agent ou les clés locales
            let res = authenticate_session(&sess, "fanta", Some("un_faux_mot_de_passe"), None);
            assert!(res.is_ok(), "L'authentification par repli sur clé devrait réussir : {:?}", res);
            assert!(sess.authenticated());
        }
    }

    #[test]
    #[ignore = "nécessite un serveur SSH accessible (voir BOBINE_TEST_SSH_HOST) en environnement de développement"]
    fn test_auth_error_message_when_password_disabled() {
        let addr = format!("{}:22", test_ssh_host());
        if let Ok(tcp) = TcpStream::connect_timeout(&addr.parse().unwrap(), Duration::from_millis(500)) {
            let mut sess = Session::new().unwrap();
            sess.set_tcp_stream(tcp);
            sess.handshake().unwrap();

            let res = authenticate_session(&sess, "utilisateur_inexistant_xyz", Some("password123"), None);
            assert!(res.is_err());
            let err = res.unwrap_err();
            println!("Message d'erreur obtenu : {err}");
            assert!(err.contains("PasswordAuthentication") || err.contains("refuse les mots de passe"));
        }
    }
}
