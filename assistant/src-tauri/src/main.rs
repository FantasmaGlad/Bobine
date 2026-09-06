// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;

use commands::discovery::scan_network;
use commands::connection::test_ssh_connection;
use commands::install::start_installation;
use commands::remote::{remote_control_playback, remote_get_health, remote_get_playback};

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            scan_network,
            test_ssh_connection,
            start_installation,
            remote_get_health,
            remote_get_playback,
            remote_control_playback
        ])
        .run(tauri::generate_context!())
        .expect("Erreur lors de l'exécution de l'assistant Bobine");
}
