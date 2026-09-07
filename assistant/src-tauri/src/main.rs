// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;

use commands::discovery::scan_network;
use commands::connection::test_ssh_connection;
use commands::install::start_installation;
use commands::version::get_app_info;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            scan_network,
            test_ssh_connection,
            start_installation,
            get_app_info
        ])
        .run(tauri::generate_context!())
        .expect("Erreur lors de l'exécution de l'assistant Bobine");
}
