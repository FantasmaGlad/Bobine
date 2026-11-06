// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod cli;
mod commands;
mod error;
mod events;

use commands::discovery::scan_network;
use commands::connection::test_ssh_connection;
use commands::install::start_installation;
use commands::ssh_auth::pick_ssh_key_file;
use commands::update::{check_assistant_update, install_assistant_update};
use commands::version::get_app_info;

fn main() {
    // `bobine-assistant scan|inspect|install|version` : ligne de commande, sans ouvrir de fenêtre.
    let args: Vec<String> = std::env::args().collect();
    if cli::is_invocation(&args) {
        std::process::exit(cli::main(args));
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            scan_network,
            test_ssh_connection,
            start_installation,
            get_app_info,
            pick_ssh_key_file,
            check_assistant_update,
            install_assistant_update
        ])
        .run(tauri::generate_context!())
        .expect("Erreur lors de l'exécution de l'assistant Bobine");
}
