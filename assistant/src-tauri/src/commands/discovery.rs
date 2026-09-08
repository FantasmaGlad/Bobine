use std::collections::HashSet;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::time::Duration;
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::net::TcpStream;
use tokio::time::timeout;

use bobine_installer_core::discovery::{os_hint_from_banner, os_hint_from_ports, subnet_hosts_v24};

/// Un appareil détecté sur le réseau — pas nécessairement une cible Bobine.
/// Réf. mission "scan réseau complet" : l'assistant affiche TOUT ce qui
/// répond (nom, IP, OS estimé, ports ouverts), pas seulement les appareils
/// SSH/Bobine — un utilisateur qui prépare un déploiement headless doit
/// pouvoir reconnaître sa borne au milieu du reste du réseau (routeur,
/// imprimante, téléphones...) plutôt que de voir une liste tronquée qui
/// pourrait laisser croire à un scan cassé ou incomplet.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveredDevice {
    pub ip: String,
    pub hostname: Option<String>,
    pub ssh_open: bool,
    pub bobine_open: bool,
    pub open_ports: Vec<u16>,
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

/// Port pratiquement toujours fermé (9, "discard") sondé sur chaque
/// candidat : une connexion *refusée* rapidement (RST reçu) prouve qu'un
/// hôte existe à cette IP même sans AUCUN service utile ouvert (téléphone,
/// imprimante verrouillée, appareil IoT...), ce qu'une simple absence de
/// réponse ne permet pas de distinguer d'une adresse tout simplement
/// inutilisée sur le sous-réseau. C'est ce qui permet d'afficher TOUS les
/// appareils vivants plutôt que seulement ceux qui exposent SSH ou Bobine.
const LIVENESS_PROBE_PORT: u16 = 9;

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

/// Sonde générique : le port TCP donné est-il ouvert (connexion réussie) ?
async fn probe_port_open(ip: Ipv4Addr, port: u16) -> bool {
    let addr = SocketAddr::new(IpAddr::V4(ip), port);
    timeout(Duration::from_millis(500), TcpStream::connect(addr))
        .await
        .map(|r| r.is_ok())
        .unwrap_or(false)
}

/// Sonde un ensemble de ports usuels (HTTP/S, partage Windows, bureau à
/// distance, AirPlay/Bonjour, impression réseau) en parallèle. Complète le
/// port 8000 (Bobine, sondé à part) pour qualifier n'importe quel appareil
/// du réseau, pas seulement les cibles Bobine.
async fn probe_common_ports(ip: Ipv4Addr) -> Vec<u16> {
    let (p80, p443, p445, p3389, p5000, p7000, p9100) = tokio::join!(
        probe_port_open(ip, 80),
        probe_port_open(ip, 443),
        probe_port_open(ip, 445),
        probe_port_open(ip, 3389),
        probe_port_open(ip, 5000),
        probe_port_open(ip, 7000),
        probe_port_open(ip, 9100),
    );
    let mut ports = Vec::new();
    if p80 {
        ports.push(80);
    }
    if p443 {
        ports.push(443);
    }
    if p445 {
        ports.push(445);
    }
    if p3389 {
        ports.push(3389);
    }
    if p5000 {
        ports.push(5000);
    }
    if p7000 {
        ports.push(7000);
    }
    if p9100 {
        ports.push(9100);
    }
    ports
}

/// Sonde si le port 8000 (API Bobine) est ouvert
async fn probe_bobine_port(ip: Ipv4Addr) -> bool {
    probe_port_open(ip, 8000).await
}

/// Un hôte existe-t-il à cette IP même sans aucun port utile ouvert ? Une
/// connexion *refusée* (RST) sur un port réputé fermé prouve la présence
/// d'un système, contrairement à un simple timeout (silence = probablement
/// rien à cette adresse).
async fn probe_liveness(ip: Ipv4Addr) -> bool {
    let addr = SocketAddr::new(IpAddr::V4(ip), LIVENESS_PROBE_PORT);
    match timeout(Duration::from_millis(500), TcpStream::connect(addr)).await {
        Ok(Ok(_)) => true,
        Ok(Err(e)) => e.kind() == std::io::ErrorKind::ConnectionRefused,
        Err(_) => false,
    }
}

/// Résolution de nom inversée (DNS/mDNS/NetBIOS selon la plateforme, via le
/// résolveur système — fonctionne aussi pour les noms `.local` sur la
/// plupart des installations Linux (nss-mdns), macOS (Bonjour) et Windows
/// (NetBIOS/LLMNR)). Best-effort : bornée dans le temps, `None` si rien
/// n'est trouvé ou si le résolveur renvoie simplement l'IP elle-même.
async fn resolve_hostname(ip: Ipv4Addr) -> Option<String> {
    let ip_addr = IpAddr::V4(ip);
    let lookup = tokio::task::spawn_blocking(move || dns_lookup::lookup_addr(&ip_addr).ok());
    match timeout(Duration::from_millis(1200), lookup).await {
        Ok(Ok(Some(name))) if name != ip.to_string() => Some(name),
        _ => None,
    }
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

            // Sonde SSH (22), Bobine (8000), un panel de ports usuels et la
            // "vivacité" générale (port fermé, RST) en parallèle pour
            // chaque hôte — un appareil est retenu dès qu'UN SEUL de ces
            // signaux répond, pas seulement SSH/Bobine.
            let (ssh_res, bobine_open, mut open_ports, alive) = tokio::join!(
                probe_ssh(ip),
                probe_bobine_port(ip),
                probe_common_ports(ip),
                probe_liveness(ip)
            );

            let ssh_open = ssh_res.is_some();
            if ssh_open {
                open_ports.push(22);
            }
            if bobine_open {
                open_ports.push(8000);
            }
            open_ports.sort_unstable();

            let is_alive = ssh_open || bobine_open || !open_ports.is_empty() || alive;
            if !is_alive {
                return None;
            }

            let hostname = resolve_hostname(ip).await;

            let os_hint = ssh_res
                .as_ref()
                .and_then(|(_, hint)| hint.clone())
                .or_else(|| os_hint_from_ports(&open_ports));

            let is_wyse_or_bobine = bobine_open
                || os_hint
                    .as_ref()
                    .map(|h| {
                        let hl = h.to_lowercase();
                        hl.contains("debian") || hl.contains("linux") || hl.contains("bobine")
                    })
                    .unwrap_or(false);

            Some(DiscoveredDevice {
                ip: ip.to_string(),
                hostname,
                ssh_open,
                bobine_open,
                open_ports,
                os_hint,
                is_wyse_or_bobine,
            })
        }));
    }

    let mut results = Vec::new();
    for task in tasks {
        if let Ok(Some(device)) = task.await {
            results.push(device);
        }
    }

    // Trie pour placer les cibles prioritaires (Debian / Bobine) en tête,
    // puis les hôtes SSH, puis le reste des appareils du réseau par IP
    // (comparaison numérique des octets — pas lexicale, sinon "10.0.0.9"
    // trierait après "10.0.0.10").
    results.sort_by(|a, b| {
        b.bobine_open
            .cmp(&a.bobine_open)
            .then_with(|| b.is_wyse_or_bobine.cmp(&a.is_wyse_or_bobine))
            .then_with(|| b.ssh_open.cmp(&a.ssh_open))
            .then_with(|| {
                let ip_a = a.ip.parse::<Ipv4Addr>().unwrap_or(Ipv4Addr::UNSPECIFIED);
                let ip_b = b.ip.parse::<Ipv4Addr>().unwrap_or(Ipv4Addr::UNSPECIFIED);
                ip_a.octets().cmp(&ip_b.octets())
            })
    });

    Ok(results)
}
