//! `bobine-devices` : sidecar de gestion des périphériques (audio, Bluetooth, Wi-Fi).
//!
//! Lancé À LA DEMANDE par le backend Bobine, sous le même compte que lui ; parle JSON-RPC 2.0 sur
//! stdin/stdout (une ligne = une requête ou une réponse), n'ouvre AUCUN port réseau et n'exécute que
//! la liste blanche de méthodes de `protocol.rs`. Fin de l'entrée standard = arrêt propre.

mod exec;
mod parse;
mod platform;
mod protocol;

use std::io::{BufRead, Write};

fn main() {
    let platform = platform::current();
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    let mut reader = stdin.lock();
    let mut line = String::new();
    loop {
        line.clear();
        match reader.read_line(&mut line) {
            Ok(0) | Err(_) => break, // le backend a fermé le canal : on s'arrête
            Ok(_) => {}
        }
        if line.len() > protocol::MAX_LINE_BYTES {
            let reply = r#"{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"Requête trop longue"}}"#;
            let _ = writeln!(out, "{reply}");
            let _ = out.flush();
            continue;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let reply = protocol::handle_line(platform.as_ref(), trimmed);
        if writeln!(out, "{reply}").is_err() || out.flush().is_err() {
            break;
        }
    }
}
