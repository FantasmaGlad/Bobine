use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::time::Duration;
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::net::TcpStream;
use tokio::time::timeout;

use bobine_installer_core::discovery::{os_hint_from_banner, subnet_hosts_v24};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveredDevice {
    pub ip: String,
    pub hostname: Option<String>,
    pub ssh_open: bool,
    pub bobine_open: bool,
    pub os_hint: Option<String>,
    pub is_wyse_or_bobine: bool,
}

/// Détecte l'IP locale de la machine hôte pour déduire le sous-réseau
fn get_local_ip() -> Option<Ipv4Addr> {
    // Tente de résoudre via une socket UDP dummy vers un DNS public
    let socket = std::net::UdpSocket::bind("0.0.0.0:0").ok()?;
    socket.connect("1.1.1.1:80").ok()?;
    match socket.local_addr().ok()?.ip() {
        IpAddr::V4(ipv4) => Some(ipv4),
        _ => None,
    }
}

/// Sonde une IP sur le port 22 et lit la bannière SSH
async fn probe_ssh(ip: Ipv4Addr) -> Option<(String, Option<String>)> {
    let addr = SocketAddr::new(IpAddr::V4(ip), 22);
    let connect_future = TcpStream::connect(addr);

    if let Ok(Ok(stream)) = timeout(Duration::from_millis(250), connect_future).await {
        let mut reader = BufReader::new(stream);
        let mut line = String::new();
        // Lit la bannière SSH envoyée par le serveur (ex: "SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3")
        if let Ok(Ok(_)) = timeout(Duration::from_millis(200), reader.read_line(&mut line)).await {
            let banner = line.trim().to_string();
            let hint = os_hint_from_banner(&banner);
            return Some((banner, hint));
        }
        return Some(("SSH-Open".to_string(), None));
    }
    None
}

/// Sonde si le port 8000 (API Bobine) est ouvert
async fn probe_bobine_port(ip: Ipv4Addr) -> bool {
    let addr = SocketAddr::new(IpAddr::V4(ip), 8000);
    timeout(Duration::from_millis(150), TcpStream::connect(addr))
        .await
        .map(|r| r.is_ok())
        .unwrap_or(false)
}

#[tauri::command]
pub async fn scan_network(custom_subnet: Option<String>) -> Result<Vec<DiscoveredDevice>, String> {
    let local_ip = if let Some(sub) = custom_subnet {
        sub.parse::<Ipv4Addr>()
            .map_err(|e| format!("Sous-réseau invalide : {e}"))?
    } else {
        get_local_ip().unwrap_or_else(|| Ipv4Addr::new(192, 168, 1, 100))
    };

    let candidates = subnet_hosts_v24(local_ip);
    let mut tasks = Vec::with_capacity(candidates.len());

    // Lance les sondes TCP en parallèle par petits groupes
    for ip in candidates {
        tasks.push(tokio::spawn(async move {
            let ssh_res = probe_ssh(ip).await;
            let bobine_open = probe_bobine_port(ip).await;

            if ssh_res.is_some() || bobine_open {
                let os_hint = ssh_res.as_ref().and_then(|(_, hint)| hint.clone());
                let is_wyse_or_bobine = bobine_open
                    || os_hint
                        .as_ref()
                        .map(|h| h.to_lowercase().contains("debian") || h.to_lowercase().contains("linux"))
                        .unwrap_or(false);

                Some(DiscoveredDevice {
                    ip: ip.to_string(),
                    hostname: None,
                    ssh_open: ssh_res.is_some(),
                    bobine_open,
                    os_hint,
                    is_wyse_or_bobine,
                })
            } else {
                None
            }
        }));
    }

    let mut results = Vec::new();
    for task in tasks {
        if let Ok(Some(device)) = task.await {
            results.push(device);
        }
    }

    // Trie pour placer les cibles prioritaires (Debian / Bobine) en tête
    results.sort_by(|a, b| {
        b.bobine_open
            .cmp(&a.bobine_open)
            .then_with(|| b.is_wyse_or_bobine.cmp(&a.is_wyse_or_bobine))
    });

    Ok(results)
}
