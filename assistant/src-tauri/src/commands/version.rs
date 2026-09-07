use serde::Serialize;

/// Version et commit du build courant, embarqués à la compilation par
/// `build.rs` (réf. mission "hiérarchie des versions" — l'assistant ne
/// pouvait pas se comparer correctement aux releases GitHub sans connaître
/// sa propre version, ce qui lui faisait proposer une "mise à jour" vers une
/// Stable en réalité plus ancienne que le build Bêta déjà installé).
#[derive(Debug, Clone, Serialize)]
pub struct AppInfo {
    pub version: String,
    pub commit: String,
}

#[tauri::command]
pub fn get_app_info() -> AppInfo {
    AppInfo {
        version: env!("BOBINE_VERSION").to_string(),
        commit: env!("BOBINE_COMMIT").to_string(),
    }
}
