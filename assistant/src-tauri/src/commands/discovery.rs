use std::collections::{HashMap, HashSet};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, ToSocketAddrs};
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;
use tokio::sync::Semaphore;
use tokio::time::timeout;

use bobine_installer_core::discovery::{
    host_range, is_scannable_ipv4, is_tunnel_interface, is_virtual_interface, os_hint_from_banner,
    os_hint_from_ports, parse_arp_a, parse_network_spec, parse_proc_net_arp, prefix_from_netmask,
};

/// Un appareil détecté sur le réseau — pas nécessairement une cible Bobine.
/// l'assistant affiche TOUT ce qui
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
    /// Le port 8000 répond ET `/api/health` a la forme d'un backend Bobine
    /// (un simple port 8000 ouvert peut être n'importe quel serveur de dev).
    pub bobine_open: bool,
    pub open_ports: Vec<u16>,
    pub os_hint: Option<String>,
    pub is_wyse_or_bobine: bool,
    /// Adresse MAC lue dans la table ARP du poste (utile pour réserver l'IP
    /// de la borne dans le routeur). Absente si l'appareil n'y figure pas.
    #[serde(default)]
    pub mac: Option<String>,
    /// Comment l'appareil a été repéré : "ports" (au moins un port a
    /// répondu), "arp" (seulement la table de voisinage : tous ses ports sont
    /// filtrés) ou "mdns" (nom `bobine.local` résolu).
    #[serde(default)]
    pub seen_via: String,
}

/// Progression diffusée pendant le scan (évènement `scan_progress`).
#[derive(Debug, Clone, Serialize)]
struct ScanProgress {
    done: usize,
    total: usize,
    found: usize,
    /// Réseaux balayés, ex. "192.168.1.0/24 (wlp3s0)" — affichés tels quels
    /// pour que l'utilisateur voie QUEL réseau est sondé.
    networks: Vec<String>,
}

/// Ports usuels sondés sur chaque hôte (HTTP/S, SSH, partage Windows, bureau
/// à distance, AirPlay/Bonjour, Bobine, impression réseau).
const COMMON_PORTS: [u16; 9] = [22, 80, 443, 445, 3389, 5000, 7000, 8000, 9100];

/// Port pratiquement toujours fermé (9, "discard") : une connexion *refusée*
/// rapidement (RST) prouve qu'un hôte existe à cette IP même sans AUCUN
/// service utile ouvert (téléphone, imprimante verrouillée, appareil IoT...).
const LIVENESS_PROBE_PORT: u16 = 9;

/// Nombre MAXIMAL de sockets ouvertes simultanément, tous hôtes confondus.
/// L'ancien code lançait 64 hôtes × une dizaine de sondes en parallèle (~700
/// sockets) : au-delà de la limite de descripteurs d'un processus graphique
/// (256 par défaut sous macOS), `connect` échouait en « Too many open files »
/// — traité comme « port fermé » — et le scan ne trouvait alors RIEN, sans
/// aucune erreur visible.
const MAX_OPEN_SOCKETS: usize = 96;
/// Nombre d'hôtes traités en même temps (chacun consomme au plus quelques
/// sockets à la fois, plafonnées par `MAX_OPEN_SOCKETS`).
const MAX_CONCURRENT_HOSTS: usize = 40;

const CONNECT_TIMEOUT: Duration = Duration::from_millis(900);

enum ProbeOutcome {
    Open(TcpStream),
    /// RST reçu : hôte présent, port fermé.
    Refused,
    Silent,
}

/// Réseaux à balayer : (ip du poste, préfixe, libellé affiché).
struct ScanPlan {
    networks: Vec<(Ipv4Addr, u8, String)>,
    local_ips: HashSet<Ipv4Addr>,
}

/// Interfaces actives du poste, classées : réseaux « physiques » d'abord ; les
/// tunnels/VPN seulement s'il n'y a rien d'autre ; jamais les interfaces de
/// conteneurs/VM ni l'auto-adressage 169.254/16 (aucun DHCP : personne à y
/// trouver). Le préfixe vient du VRAI masque de l'interface et non d'un /24
/// supposé : sur un réseau /23 ou /22 la borne pouvait être hors du /24 du
/// poste et restait invisible.
fn plan_from_interfaces() -> ScanPlan {
    let mut primary = Vec::new();
    let mut tunnels = Vec::new();
    let mut local_ips = HashSet::new();

    if let Ok(interfaces) = if_addrs::get_if_addrs() {
        for iface in interfaces {
            let if_addrs::IfAddr::V4(v4) = &iface.addr else { continue };
            if iface.is_loopback() || !is_scannable_ipv4(v4.ip) {
                continue;
            }
            local_ips.insert(v4.ip);
            if is_virtual_interface(&iface.name) {
                continue;
            }
            let prefix = prefix_from_netmask(v4.netmask);
            let label = format!("{}/{} ({})", network_of(v4.ip, prefix), prefix.max(22), iface.name);
            let entry = (v4.ip, prefix, label);
            if is_tunnel_interface(&iface.name, v4.ip) {
                tunnels.push(entry);
            } else {
                primary.push(entry);
            }
        }
    }

    let mut networks = if primary.is_empty() { tunnels } else { primary };
    if networks.is_empty() {
        // Repli : énumération impossible (permissions, plateforme exotique) —
        // IP de la route par défaut via une astuce UDP (aucun paquet émis).
        if let Some(ip) = default_route_ip() {
            local_ips.insert(ip);
            networks.push((ip, 24, format!("{}/24 (route par défaut)", network_of(ip, 24))));
        }
    }
    ScanPlan { networks, local_ips }
}

fn network_of(ip: Ipv4Addr, prefix: u8) -> Ipv4Addr {
    let prefix = prefix.clamp(22, 32);
    let mask: u32 = u32::MAX << (32 - prefix);
    Ipv4Addr::from(u32::from(ip) & mask)
}

fn default_route_ip() -> Option<Ipv4Addr> {
    let socket = std::net::UdpSocket::bind("0.0.0.0:0").ok()?;
    socket.connect("1.1.1.1:80").ok()?;
    match socket.local_addr().ok()?.ip() {
        IpAddr::V4(ipv4) if is_scannable_ipv4(ipv4) => Some(ipv4),
        _ => None,
    }
}

async fn connect_probe(sockets: &Semaphore, ip: Ipv4Addr, port: u16) -> ProbeOutcome {
    let Ok(_permit) = sockets.acquire().await else { return ProbeOutcome::Silent };
    let addr = SocketAddr::new(IpAddr::V4(ip), port);
    match timeout(CONNECT_TIMEOUT, TcpStream::connect(addr)).await {
        Ok(Ok(stream)) => ProbeOutcome::Open(stream),
        Ok(Err(e)) if e.kind() == std::io::ErrorKind::ConnectionRefused => ProbeOutcome::Refused,
        _ => ProbeOutcome::Silent,
    }
}

/// Lit la bannière SSH (ex. "SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3").
async fn read_ssh_banner(stream: TcpStream) -> String {
    let mut reader = BufReader::new(stream);
    let mut line = String::new();
    match timeout(Duration::from_millis(500), reader.read_line(&mut line)).await {
        Ok(Ok(_)) if !line.trim().is_empty() => line.trim().to_string(),
        _ => "SSH-Open".to_string(),
    }
}

/// Le port 8000 est-il bien un backend Bobine ? `GET /api/health` renvoie un
/// JSON listant les `components` (base de données, kiosque) — signature
/// suffisante pour ne pas prendre n'importe quel serveur de dev pour une borne.
async fn confirm_bobine(mut stream: TcpStream) -> bool {
    let request = b"GET /api/health HTTP/1.0\r\nHost: bobine\r\nConnection: close\r\n\r\n";
    if timeout(Duration::from_millis(600), stream.write_all(request)).await.is_err() {
        return false;
    }
    let mut buf = vec![0u8; 1024];
    match timeout(Duration::from_millis(900), stream.read(&mut buf)).await {
        Ok(Ok(n)) if n > 0 => {
            let text = String::from_utf8_lossy(&buf[..n]);
            text.contains("\"components\"")
        }
        _ => false,
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

/// Sonde complète d'un hôte. `None` si rien n'indique qu'il existe.
async fn probe_host(sockets: Arc<Semaphore>, ip: Ipv4Addr) -> Option<DiscoveredDevice> {
    let mut handles = Vec::with_capacity(COMMON_PORTS.len() + 1);
    for port in COMMON_PORTS.iter().copied().chain(std::iter::once(LIVENESS_PROBE_PORT)) {
        let sockets = sockets.clone();
        handles.push(tokio::spawn(async move { (port, connect_probe(&sockets, ip, port).await) }));
    }

    let mut open_ports: Vec<u16> = Vec::new();
    let mut ssh_banner: Option<String> = None;
    let mut bobine_open = false;
    let mut alive = false;
    for handle in handles {
        let Ok((port, outcome)) = handle.await else { continue };
        match outcome {
            ProbeOutcome::Open(stream) => {
                alive = true;
                if port == LIVENESS_PROBE_PORT {
                    continue;
                }
                open_ports.push(port);
                if port == 22 {
                    ssh_banner = Some(read_ssh_banner(stream).await);
                } else if port == 8000 {
                    bobine_open = confirm_bobine(stream).await;
                }
            }
            ProbeOutcome::Refused => alive = true,
            ProbeOutcome::Silent => {}
        }
    }
    if !alive {
        return None;
    }
    open_ports.sort_unstable();

    let ssh_open = ssh_banner.is_some();
    let os_hint = ssh_banner
        .as_deref()
        .and_then(os_hint_from_banner)
        .or_else(|| os_hint_from_ports(&open_ports));
    Some(build_device(ip, None, ssh_open, bobine_open, open_ports, os_hint, "ports"))
}

fn build_device(
    ip: Ipv4Addr,
    hostname: Option<String>,
    ssh_open: bool,
    bobine_open: bool,
    open_ports: Vec<u16>,
    os_hint: Option<String>,
    seen_via: &str,
) -> DiscoveredDevice {
    let is_wyse_or_bobine = bobine_open
        || os_hint
            .as_ref()
            .map(|h| {
                let hl = h.to_lowercase();
                hl.contains("debian") || hl.contains("linux") || hl.contains("bobine")
            })
            .unwrap_or(false);
    DiscoveredDevice {
        ip: ip.to_string(),
        hostname,
        ssh_open,
        bobine_open,
        open_ports,
        os_hint,
        is_wyse_or_bobine,
        mac: None,
        seen_via: seen_via.to_string(),
    }
}

/// Table de voisinage ARP du poste (IP -> MAC). Lue APRÈS le balayage : le
/// noyau y inscrit tout hôte qui a répondu à la résolution ARP, même si
/// TOUS ses ports sont filtrés (pare-feu qui ignore les paquets) — cas où
/// aucune sonde TCP ne peut le voir.
fn read_arp_table() -> HashMap<Ipv4Addr, String> {
    #[cfg(target_os = "linux")]
    {
        if let Ok(content) = std::fs::read_to_string("/proc/net/arp") {
            return parse_proc_net_arp(&content).into_iter().collect();
        }
    }
    let mut command = std::process::Command::new("arp");
    command.arg("-a");
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW : évite le clignotement d'une console noire.
        command.creation_flags(0x0800_0000);
    }
    match command.output() {
        Ok(out) if out.status.success() => {
            parse_arp_a(&String::from_utf8_lossy(&out.stdout)).into_iter().collect()
        }
        _ => HashMap::new(),
    }
}

/// Nom `bobine.local` (publié par l'appliance via avahi et par les profils
/// de bureau via zeroconf) résolu par le système : trouve la borne même si
/// elle est sur un autre sous-réseau relayé par mDNS, et sert d'indice
/// supplémentaire quand plusieurs appareils répondent.
async fn resolve_bobine_local() -> Option<Ipv4Addr> {
    let lookup = tokio::task::spawn_blocking(|| {
        ("bobine.local", 8000u16)
            .to_socket_addrs()
            .ok()?
            .find_map(|addr| match addr.ip() {
                IpAddr::V4(ip) if is_scannable_ipv4(ip) => Some(ip),
                _ => None,
            })
    });
    timeout(Duration::from_millis(1500), lookup).await.ok()?.ok()?
}

#[tauri::command]
pub async fn scan_network(app: AppHandle, custom_subnet: Option<String>) -> Result<Vec<DiscoveredDevice>, String> {
    let mut plan = plan_from_interfaces();

    if let Some(spec) = custom_subnet.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        let (ip, prefix) = parse_network_spec(spec).ok_or_else(|| {
            "Réseau invalide : saisissez une adresse (192.168.2.10) ou un réseau (192.168.2.0/24).".to_string()
        })?;
        plan.networks = vec![(ip, prefix, format!("{}/{} (saisi)", network_of(ip, prefix), prefix.max(22)))];
    }
    if plan.networks.is_empty() {
        return Err(
            "Aucune interface réseau active détectée : branchez-vous au même réseau que la borne \
             (Wi-Fi ou Ethernet), ou saisissez l'adresse de la borne manuellement."
                .to_string(),
        );
    }

    // Plusieurs interfaces actives (Wi-Fi + Ethernet, VPN...) : on sonde le
    // réseau de CHACUNE, en dédoublonnant les chevauchements.
    let mut seen = HashSet::new();
    let mut candidates: Vec<Ipv4Addr> = Vec::new();
    for (ip, prefix, _) in &plan.networks {
        for host in host_range(*ip, *prefix) {
            if !plan.local_ips.contains(&host) && seen.insert(host) {
                candidates.push(host);
            }
        }
    }
    candidates.sort();
    let network_labels: Vec<String> = plan.networks.iter().map(|(_, _, label)| label.clone()).collect();
    let total = candidates.len();

    let sockets = Arc::new(Semaphore::new(MAX_OPEN_SOCKETS));
    let hosts_gate = Arc::new(Semaphore::new(MAX_CONCURRENT_HOSTS));
    let mut tasks = tokio::task::JoinSet::new();
    for ip in candidates.iter().copied() {
        let sockets = sockets.clone();
        let hosts_gate = hosts_gate.clone();
        tasks.spawn(async move {
            let _slot = hosts_gate.acquire_owned().await.ok()?;
            probe_host(sockets, ip).await
        });
    }

    let mut results: Vec<DiscoveredDevice> = Vec::new();
    let mut done = 0usize;
    let mut last_emit = Instant::now();
    while let Some(joined) = tasks.join_next().await {
        done += 1;
        if let Ok(Some(device)) = joined {
            app.emit("scan_device", &device).ok();
            results.push(device);
        }
        // Au plus ~8 mises à jour par seconde : fluide sans noyer l'IHM.
        if last_emit.elapsed() >= Duration::from_millis(120) || done == total {
            last_emit = Instant::now();
            app.emit(
                "scan_progress",
                ScanProgress { done, total, found: results.len(), networks: network_labels.clone() },
            )
            .ok();
        }
    }

    // Second regard, une fois les sondes passées (le noyau a désormais résolu
    // l'ARP de tous les hôtes présents) : MAC des appareils trouvés, et
    // appareils invisibles aux ports (tout filtré).
    let arp = read_arp_table();
    let known: HashSet<Ipv4Addr> = results.iter().filter_map(|d| d.ip.parse().ok()).collect();
    for device in results.iter_mut() {
        if let Ok(ip) = device.ip.parse::<Ipv4Addr>() {
            device.mac = arp.get(&ip).cloned();
        }
    }
    let scanned: HashSet<Ipv4Addr> = candidates.iter().copied().collect();
    for (ip, mac) in &arp {
        if scanned.contains(ip) && !known.contains(ip) {
            let mut device = build_device(*ip, None, false, false, Vec::new(), None, "arp");
            device.mac = Some(mac.clone());
            app.emit("scan_device", &device).ok();
            results.push(device);
        }
    }

    // Nom mDNS `bobine.local` : même hors des réseaux balayés.
    if let Some(mdns_ip) = resolve_bobine_local().await {
        match results.iter_mut().find(|d| d.ip == mdns_ip.to_string()) {
            Some(device) => {
                device.is_wyse_or_bobine = true;
                if device.os_hint.is_none() {
                    device.os_hint = Some("Bobine (bobine.local)".to_string());
                }
            }
            None => {
                let mut device = build_device(
                    mdns_ip, Some("bobine.local".to_string()), false, false, Vec::new(),
                    Some("Bobine (bobine.local)".to_string()), "mdns",
                );
                device.is_wyse_or_bobine = true;
                app.emit("scan_device", &device).ok();
                results.push(device);
            }
        }
    }

    // Noms d'hôte, en parallèle (1,2 s max chacun) pour les seuls appareils
    // retenus — pas pour les ~1000 adresses vides.
    let mut name_tasks = tokio::task::JoinSet::new();
    for (index, device) in results.iter().enumerate() {
        if device.hostname.is_none() {
            if let Ok(ip) = device.ip.parse::<Ipv4Addr>() {
                name_tasks.spawn(async move { (index, resolve_hostname(ip).await) });
            }
        }
    }
    while let Some(joined) = name_tasks.join_next().await {
        if let Ok((index, Some(name))) = joined {
            results[index].hostname = Some(name);
        }
    }

    // Trie pour placer les cibles prioritaires (Bobine confirmée, puis
    // Debian/Linux, puis hôtes SSH) en tête, le reste par IP (comparaison
    // numérique des octets — pas lexicale, sinon "10.0.0.9" trierait après
    // "10.0.0.10").
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

    app.emit(
        "scan_progress",
        ScanProgress { done: total, total, found: results.len(), networks: network_labels },
    )
    .ok();
    Ok(results)
}
