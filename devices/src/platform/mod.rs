//! Backends par système d'exploitation. Tous compilent partout (ils ne font qu'appeler des outils
//! au moment de l'exécution) ; `current()` choisit celui de la machine.

pub mod macos;
pub mod unsupported;
pub mod windows;

use crate::protocol::Platform;

pub fn current() -> Box<dyn Platform> {
    if cfg!(target_os = "macos") {
        Box::new(macos::MacOs::new())
    } else if cfg!(target_os = "windows") {
        Box::new(windows::Windows::new())
    } else {
        Box::new(unsupported::Unsupported)
    }
}
