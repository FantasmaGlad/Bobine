use std::collections::HashSet;
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

/// Détecte les IP locales (IPv4, non loopback) de TOUTES les interfaces
/// réseau actives de la machine hôte — pas seulement celle de la route par
/// défaut. Un poste admin avec VPN, Docker ou plusieurs cartes réseau actives
/// verrait sinon le scan cibler le mauvais sous-réseau et manquer le mini PC
/// (réf. retour utilisateur "n'arrive pas à scanner le réseau").
fn get_local_ipv4_addrs() -> Vec<Ipv4Addr> {
    match if_addrs::get_if_addrs() {
        Ok(interfaces) => interfaces
            .into_iter()
            .filter(|iface| !iface.is_loopback())
            .filter_map(|iface| match iface.ip() {
                IpAddr::V4(ipv4) => Some(ipv4),
                IpAddr::V6(_) => None,
            })
            .collect(),
        Err(_) => Vec::new(),
    }
}

/// Repli si l'énumération des interfaces échoue (permissions, plateforme
/// exotique...) : déduit l'IP de la route par défaut via une astuce UDP.
fn get_default_route_ip() -> Option<Ipv4Addr> {
    let socket = std::net::UdpSocket::bind("0.0.0.0:0").ok()?;
    socket.connect("1.1.1.1:80").ok()?;
    match socket.local_addr().ok()?.ip() {
        IpAddr::V4(ipv4) => Some(ipv4),
        _ => None,
    }
}

use std::sync::Arc;
use tokio::sync::Semaphore;

/// Sonde une IP sur le port 22 et lit la bannière SSH
async fn probe_ssh(ip: Ipv4Addr) -> Option<(String, Option<String>)> {
    let addr = SocketAddr::new(IpAddr::V4(ip), 22);
    let connect_future = TcpStream::connect(addr);

    // Timeout de 800ms : suffisant pour l'ARP + handshake TCP sur Wi-Fi/Ethernet
    // sans bloquer indéfiniment sur les adresses vides.
    if let Ok(Ok(stream)) = timeout(Duration::from_millis(800), connect_future).await {
        let mut reader = BufReader::new(stream);
        let mut line = String::new();
        // Lit la bannière SSH envoyée par le serveur (ex: "SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3")
        if let Ok(Ok(_)) = timeout(Duration::from_millis(400), reader.read_line(&mut line)).await {
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
    timeout(Duration::from_millis(600), TcpStream::connect(addr))
        .await
        .map(|r| r.is_ok())
        .unwrap_or(false)
}

#[tauri::command]
pub async fn scan_network(custom_subnet: Option<String>) -> Result<Vec<DiscoveredDevice>, String> {
    let local_ips: Vec<Ipv4Addr> = if let Some(sub) = custom_subnet {
        vec![sub
            .parse::<Ipv4Addr>()
            .map_err(|e| format!("Sous-réseau invalide : {e}"))?]
    } else {
        let mut ips = get_local_ipv4_addrs();
        if ips.is_empty() {
            ips.push(get_default_route_ip().unwrap_or_else(|| Ipv4Addr::new(192, 168, 1, 100)));
        }
        ips
    };

    // Un poste admin a souvent plusieurs interfaces actives à la fois
    // (Wi-Fi + Ethernet, VPN, Docker...) : on sonde le /24 de CHACUNE plutôt
    // que de deviner laquelle contient le mini PC, en dédoublonnant les
    // candidats qui se recouvriraient entre deux interfaces.
    let local_ips_set: HashSet<Ipv4Addr> = local_ips.iter().copied().collect();
    let mut candidates_set: HashSet<Ipv4Addr> = HashSet::new();
    for local_ip in &local_ips {
        candidates_set.extend(subnet_hosts_v24(*local_ip));
    }
    let mut candidates: Vec<Ipv4Addr> = candidates_set
        .into_iter()
        .filter(|ip| !local_ips_set.contains(ip))
        .collect();

    // Tri stable pour une exploration cohérente
    candidates.sort();

    // Limiteur de concurrence (64 sondes simultanées max) pour éviter
    // de saturer la table ARP du noyau Linux ou le switch/routeur Wi-Fi
    // par des rafales massives de requêtes broadcast.
    let semaphore = Arc::new(Semaphore::new(64));
    let mut tasks = Vec::with_capacity(candidates.len());

    for ip in candidates {
        let sem = semaphore.clone();
        tasks.push(tokio::spawn(async move {
            let _permit = sem.acquire_owned().await.ok()?;

            // Sonde SSH (22) et Bobine (8000) en parallèle pour chaque hôte
            let (ssh_res, bobine_open) = tokio::join!(
                probe_ssh(ip),
                probe_bobine_port(ip)
            );

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
