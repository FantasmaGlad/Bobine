//! Événements de progression (scan, installation, mise à jour) : vers la fenêtre de l'interface quand l'assistant
//! tourne en application, vers la console quand il tourne en ligne de commande (`cli.rs`). Le scan et l'installation
//! n'ont ainsi qu'une seule implémentation pour les deux.

use serde::Serialize;
use serde_json::Value;
use tauri::Emitter;

pub trait Events: Send + Sync {
    fn send(&self, name: &str, payload: Value);
}

/// Sérialise puis envoie ; un événement qui ne se sérialise pas est ignoré, comme un `emit` en échec.
pub fn send<T: Serialize + ?Sized>(events: &dyn Events, name: &str, payload: &T) {
    if let Ok(value) = serde_json::to_value(payload) {
        events.send(name, value);
    }
}

impl Events for tauri::AppHandle {
    fn send(&self, name: &str, payload: Value) {
        let _ = self.emit(name, payload);
    }
}
