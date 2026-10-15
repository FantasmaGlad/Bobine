use serde::Serialize;

/// Version et commit du build courant, embarqués à la compilation par
/// `build.rs`.
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
