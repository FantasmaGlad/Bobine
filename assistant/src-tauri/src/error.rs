//! Erreur des opérations partagées par l'interface et la ligne de commande : la cause (cible injoignable,
//! authentification refusée, autre échec) donne le code de sortie de `bobine-assistant` ; l'interface n'en garde que
//! le message.

use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AssistantError {
    /// Nom introuvable, connexion refusée ou expirée, port sans serveur SSH.
    Unreachable(String),
    /// Le serveur SSH répond mais refuse l'authentification.
    Refused(String),
    /// Tout le reste (commande distante, installation interrompue...).
    Failed(String),
    /// Demande incomplète ou contradictoire (ligne de commande) : rien n'a été tenté.
    Usage(String),
}

impl AssistantError {
    pub fn message(&self) -> &str {
        match self {
            Self::Unreachable(m) | Self::Refused(m) | Self::Failed(m) | Self::Usage(m) => m,
        }
    }
}

impl fmt::Display for AssistantError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.message())
    }
}

impl From<String> for AssistantError {
    fn from(message: String) -> Self {
        Self::Failed(message)
    }
}

impl From<AssistantError> for String {
    fn from(error: AssistantError) -> Self {
        error.message().to_string()
    }
}
