//! Cœur logique de l'assistant d'installation Bobine.
//!
//! Cette bibliothèque ne fait **aucune** entrée/sortie (pas de SSH, pas de
//! scan réseau, pas de GUI) : elle regroupe la logique *pure* et testable qui
//! sera pilotée par l'IHM Tauri au jalon J2.
//!
//! Modules :
//! - [`progress`] : parse le flux `install.sh --progress=json` (le contrat
//!   machine de l'installateur) en évènements typés + un état de progression prêt à
//!   afficher (barre, libellé courant, phase, erreur).
//! - [`orchestrate`] : construit la commande shell exécutée sur la cible via
//!   SSH pour dérouler `install.sh` (élévation `sudo` ou `su - --as-user`),
//!   sans jamais embarquer de mot de passe.
//! - [`privilege`] : arbre de décision de l'amorçage des privilèges à
//!   partir des sondes `command -v sudo` / `sudo -n true`.
//! - [`discovery`] : arithmétique de découverte réseau (sous-réseau /24 à
//!   sonder) et modèle de candidat.

pub mod discovery;
pub mod orchestrate;
pub mod privilege;
pub mod progress;
