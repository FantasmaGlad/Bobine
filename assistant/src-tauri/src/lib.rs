//! Assistant d'installation : interface Tauri commune au bureau et à Android, ligne de commande sur le bureau.

#[cfg(desktop)]
pub mod cli;
mod commands;
mod error;
mod events;

use commands::discovery::scan_network;
use commands::connection::test_ssh_connection;
use commands::host_key::{ssh_host_key, trust_ssh_host_key};
use commands::install::start_installation;
use commands::ssh_auth::pick_ssh_key_file;
use commands::update::{check_assistant_update, install_assistant_update};
use commands::version::get_app_info;

/// Interface graphique ; sur Android, point d'entrée appelé par l'activité principale.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default().plugin(tauri_plugin_dialog::init());
    #[cfg(desktop)]
    let builder = builder.plugin(tauri_plugin_updater::Builder::new().build());
    builder
        .setup(|_app| {
            // Android n'a pas de dossier personnel : clés d'hôte connues (`.ssh/known_hosts`) dans le dossier privé de
            // l'application, avant toute connexion.
            #[cfg(mobile)]
            {
                use tauri::Manager;
                if std::env::var_os("HOME").is_none() {
                    std::env::set_var("HOME", _app.path().app_data_dir()?);
                }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            scan_network,
            test_ssh_connection,
            start_installation,
            get_app_info,
            pick_ssh_key_file,
            check_assistant_update,
            ssh_host_key,
            trust_ssh_host_key,
            install_assistant_update
        ])
        .run(context())
        .expect("Erreur lors de l'exécution de l'assistant Bobine");
}

/// Configuration et ressources embarquées, partagées par l'interface et `bobine-assistant update`.
pub(crate) fn context() -> tauri::Context<tauri::Wry> {
    tauri::generate_context!()
}
