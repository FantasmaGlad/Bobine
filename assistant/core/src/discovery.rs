//! Arithmétique de découverte réseau.
//!
//! Logique **pure** uniquement : déduire le `/24` local à sonder à partir de
//! l'IP du poste admin, et modéliser un candidat. Le scan effectif (port 22,
//! bannière SSH) et le mDNS sont des E/S, réalisées par l'IHM au jalon J2 ;
//! [`os_hint_from_banner`] les aide à qualifier ce qu'ils trouvent.

use std::net::Ipv4Addr;

/// Adresse réseau du `/24` contenant `ip` (dernier octet mis à 0).
pub fn network_v24(ip: Ipv4Addr) -> Ipv4Addr {
    let o = ip.octets();
    Ipv4Addr::new(o[0], o[1], o[2], 0)
}

/// Hôtes candidats d'un `/24` (`.1`..=`.254`), en excluant l'IP du poste admin.
///
/// On saute l'adresse réseau (`.0`) et le broadcast (`.255`), ainsi que l'IP
/// locale (inutile de se sonder soi-même).
pub fn subnet_hosts_v24(local_ip: Ipv4Addr) -> Vec<Ipv4Addr> {
    let o = local_ip.octets();
    (1u8..=254)
        .map(|host| Ipv4Addr::new(o[0], o[1], o[2], host))
        .filter(|ip| *ip != local_ip)
        .collect()
}

/// Plus petit préfixe réellement balayé : /22 = 1022 hôtes, soit quelques
/// secondes de scan. Un réseau plus vaste (/16 d'entreprise, /8 d'un VPN) ne
/// peut pas être balayé en entier ; on se limite alors au bloc /22 qui
/// contient l'IP du poste admin — là où se trouve, en pratique, la borne.
pub const MIN_SCAN_PREFIX: u8 = 22;

/// Préfixe CIDR (0..=32) déduit d'un masque de sous-réseau IPv4.
pub fn prefix_from_netmask(mask: Ipv4Addr) -> u8 {
    u32::from(mask).count_ones() as u8
}

/// Hôtes à sonder pour le réseau `ip/prefix` : tous les hôtes du bloc (réseau
/// et broadcast exclus), sans l'IP du poste admin. Les réseaux plus grands que
/// [`MIN_SCAN_PREFIX`] sont ramenés au bloc /22 contenant `ip` ; un /31 ou /32
/// (liaison point à point) ne donne aucun hôte.
///
/// Remplace l'ancien balayage figé d'un `/24` : sur un réseau `/23` ou `/22`
/// (box opérateur, Wi-Fi d'immeuble, réseau de salle de sport étendu), la
/// borne pouvait se trouver hors du `/24` du poste et n'était jamais vue.
pub fn host_range(ip: Ipv4Addr, prefix: u8) -> Vec<Ipv4Addr> {
    let prefix = prefix.clamp(MIN_SCAN_PREFIX, 32);
    if prefix >= 31 {
        return Vec::new();
    }
    let mask: u32 = u32::MAX << (32 - prefix);
    let network = u32::from(ip) & mask;
    let broadcast = network | !mask;
    ((network + 1)..broadcast)
        .map(Ipv4Addr::from)
        .filter(|candidate| *candidate != ip)
        .collect()
}

/// Analyse `a.b.c.d` ou `a.b.c.d/nn` (saisie manuelle d'un autre réseau à
/// balayer). Sans suffixe : bloc `/24`, la convention des réseaux domestiques.
pub fn parse_network_spec(spec: &str) -> Option<(Ipv4Addr, u8)> {
    let spec = spec.trim();
    let (addr, prefix) = match spec.split_once('/') {
        Some((a, p)) => (a, p.trim().parse::<u8>().ok()?),
        None => (spec, 24),
    };
    if prefix > 32 {
        return None;
    }
    Some((addr.trim().parse::<Ipv4Addr>().ok()?, prefix))
}

/// L'adresse peut-elle appartenir à un réseau local à balayer ? Écarte la
/// boucle locale, l'auto-adressage 169.254/16 (aucun DHCP : personne à
/// trouver), le multicast et l'adresse nulle.
pub fn is_scannable_ipv4(ip: Ipv4Addr) -> bool {
    !(ip.is_loopback() || ip.is_link_local() || ip.is_multicast() || ip.is_unspecified() || ip.is_broadcast())
}

/// Interface virtuelle (conteneurs, machines virtuelles) : son réseau ne
/// contient jamais la borne, et le balayer ralentit le scan pour rien.
pub fn is_virtual_interface(name: &str) -> bool {
    let n = name.to_ascii_lowercase();
    ["docker", "br-", "veth", "virbr", "vmnet", "vboxnet", "vethernet", "cni", "flannel", "podman", "lxc", "lxd"]
        .iter()
        .any(|prefix| n.starts_with(prefix))
}

/// Interface de tunnel/VPN : balayée seulement s'il n'y a rien d'autre.
pub fn is_tunnel_interface(name: &str, ip: Ipv4Addr) -> bool {
    let n = name.to_ascii_lowercase();
    let by_name = ["tun", "tap", "utun", "wg", "tailscale", "zt", "ppp", "ipsec", "awdl", "llw"]
        .iter()
        .any(|prefix| n.starts_with(prefix));
    // 100.64.0.0/10 : espace CGNAT, utilisé par Tailscale et les opérateurs.
    let o = ip.octets();
    by_name || (o[0] == 100 && (64..=127).contains(&o[1]))
}

/// Entrées de la table de voisinage ARP du noyau : IP -> adresse MAC.
///
/// Intérêt : l'ARP est résolu par le NOYAU avant tout paquet TCP, donc un
/// appareil dont TOUS les ports sont filtrés (pare-feu `drop`) y figure quand
/// même après la tentative de connexion — aucune sonde de port ne peut le
/// révéler autrement.
pub fn parse_proc_net_arp(content: &str) -> Vec<(Ipv4Addr, String)> {
    content
        .lines()
        .skip(1) // en-tête : IP address / HW type / Flags / HW address …
        .filter_map(|line| {
            let cols: Vec<&str> = line.split_whitespace().collect();
            if cols.len() < 4 {
                return None;
            }
            let ip = cols[0].parse::<Ipv4Addr>().ok()?;
            let flags = u32::from_str_radix(cols[2].trim_start_matches("0x"), 16).ok()?;
            let mac = cols[3];
            // 0x2 = entrée complète ; MAC nulle = résolution en échec.
            if flags & 0x2 == 0 || mac == "00:00:00:00:00:00" {
                return None;
            }
            Some((ip, mac.to_ascii_lowercase()))
        })
        .collect()
}

/// Sortie de `arp -a` (macOS : `? (192.168.1.5) at aa:bb:cc:dd:ee:ff on en0 …`,
/// Windows : `  192.168.1.5   aa-bb-cc-dd-ee-ff   dynamique`). Les entrées
/// incomplètes (`(incomplete)`) et le broadcast sont ignorés.
pub fn parse_arp_a(content: &str) -> Vec<(Ipv4Addr, String)> {
    let mut out = Vec::new();
    for line in content.lines() {
        let lower = line.to_ascii_lowercase();
        if lower.contains("incomplete") || lower.contains("ff:ff:ff:ff:ff:ff") || lower.contains("ff-ff-ff-ff-ff-ff") {
            continue;
        }
        let ip = line
            .split(|c: char| c.is_whitespace() || c == '(' || c == ')')
            .find_map(|tok| tok.parse::<Ipv4Addr>().ok());
        let mac = line
            .split(|c: char| c.is_whitespace() || c == '(' || c == ')')
            .find(|tok| looks_like_mac(tok));
        if let (Some(ip), Some(mac)) = (ip, mac) {
            out.push((ip, mac.replace('-', ":").to_ascii_lowercase()));
        }
    }
    out
}

fn looks_like_mac(tok: &str) -> bool {
    let sep = if tok.contains(':') { ':' } else if tok.contains('-') { '-' } else { return false };
    let parts: Vec<&str> = tok.split(sep).collect();
    parts.len() == 6 && parts.iter().all(|p| (1..=2).contains(&p.len()) && p.chars().all(|c| c.is_ascii_hexdigit()))
}

/// Un candidat trouvé sur le réseau. Les champs optionnels se remplissent
/// au fil des sondes (résolution de nom, bannière SSH…).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Candidate {
    pub ip: Ipv4Addr,
    pub hostname: Option<String>,
    pub ssh_banner: Option<String>,
    pub os_hint: Option<String>,
}

impl Candidate {
    /// Candidat minimal : juste une IP joignable sur le port 22.
    pub fn new(ip: Ipv4Addr) -> Self {
        Candidate {
            ip,
            hostname: None,
            ssh_banner: None,
            os_hint: None,
        }
    }

    /// Renseigne la bannière SSH et en déduit l'indice d'OS.
    pub fn with_ssh_banner(mut self, banner: impl Into<String>) -> Self {
        let banner = banner.into();
        self.os_hint = os_hint_from_banner(&banner);
        self.ssh_banner = Some(banner);
        self
    }
}

/// Indice d'OS grossier déduit d'une bannière SSH (repli `None`).
///
/// Ex. `SSH-2.0-OpenSSH_9.2p1 Debian-2` → `Some("Debian")`.
pub fn os_hint_from_banner(banner: &str) -> Option<String> {
    let b = banner.to_ascii_lowercase();
    if b.contains("raspbian") {
        Some("Raspberry Pi OS".to_string())
    } else if b.contains("ubuntu") {
        Some("Ubuntu".to_string())
    } else if b.contains("debian") {
        Some("Debian".to_string())
    } else if b.contains("openssh") {
        Some("Linux/OpenSSH".to_string())
    } else {
        None
    }
}

/// Indice d'OS de repli déduit des ports TCP ouverts, pour les appareils qui
/// répondent sur le réseau mais n'exposent pas SSH (imprimantes, routeurs,
/// postes Windows, télévisions...). Beaucoup moins fiable qu'une bannière SSH
/// (des heuristiques, pas une identification) — n'intervient qu'en dernier
/// recours quand [`os_hint_from_banner`] n'a rien donné (pas de port 22).
/// Ordre de vérification volontairement du plus spécifique au plus générique.
pub fn os_hint_from_ports(ports: &[u16]) -> Option<String> {
    if ports.contains(&3389) {
        Some("Windows (Bureau à distance)".to_string())
    } else if ports.contains(&445) || ports.contains(&139) {
        Some("Windows / Partage Samba".to_string())
    } else if ports.contains(&5000) && ports.contains(&7000) {
        Some("Apple (AirPlay)".to_string())
    } else if ports.contains(&9100) {
        Some("Imprimante réseau".to_string())
    } else if ports.contains(&8000) {
        Some("Bobine (sans SSH)".to_string())
    } else if ports.contains(&80) || ports.contains(&443) {
        Some("Appareil avec interface web".to_string())
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn network_address_zeroes_last_octet() {
        assert_eq!(
            network_v24(Ipv4Addr::new(10, 0, 0, 30)),
            Ipv4Addr::new(10, 0, 0, 0)
        );
        assert_eq!(
            network_v24(Ipv4Addr::new(192, 168, 1, 42)),
            Ipv4Addr::new(192, 168, 1, 0)
        );
    }

    #[test]
    fn subnet_excludes_self_network_and_broadcast() {
        let hosts = subnet_hosts_v24(Ipv4Addr::new(10, 0, 0, 30));
        assert_eq!(hosts.len(), 253); // 254 hôtes moins soi-même
        assert!(!hosts.contains(&Ipv4Addr::new(10, 0, 0, 30))); // pas soi
        assert!(!hosts.contains(&Ipv4Addr::new(10, 0, 0, 0))); // pas le réseau
        assert!(!hosts.contains(&Ipv4Addr::new(10, 0, 0, 255))); // pas le broadcast
        assert!(hosts.contains(&Ipv4Addr::new(10, 0, 0, 1)));
        assert!(hosts.contains(&Ipv4Addr::new(10, 0, 0, 254)));
    }

    #[test]
    fn os_hint_recognises_common_banners() {
        assert_eq!(
            os_hint_from_banner("SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u2"),
            Some("Debian".to_string())
        );
        assert_eq!(
            os_hint_from_banner("SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.1"),
            Some("Ubuntu".to_string())
        );
        // OpenSSH générique sans distro identifiable.
        assert_eq!(
            os_hint_from_banner("SSH-2.0-OpenSSH_for_Windows_8.1"),
            Some("Linux/OpenSSH".to_string())
        );
        assert_eq!(os_hint_from_banner("SSH-2.0-dropbear"), None);
    }

    #[test]
    fn os_hint_from_ports_prioritises_most_specific_signal() {
        assert_eq!(
            os_hint_from_ports(&[80, 445, 3389]),
            Some("Windows (Bureau à distance)".to_string())
        );
        assert_eq!(
            os_hint_from_ports(&[445]),
            Some("Windows / Partage Samba".to_string())
        );
        assert_eq!(os_hint_from_ports(&[9100]), Some("Imprimante réseau".to_string()));
        assert_eq!(os_hint_from_ports(&[8000]), Some("Bobine (sans SSH)".to_string()));
        assert_eq!(os_hint_from_ports(&[443]), Some("Appareil avec interface web".to_string()));
        assert_eq!(os_hint_from_ports(&[]), None);
    }

    #[test]
    fn host_range_follows_the_real_netmask() {
        let ip = Ipv4Addr::new(192, 168, 1, 77);
        // /24 : 253 hôtes (254 moins soi-même), comme avant.
        assert_eq!(host_range(ip, 24).len(), 253);
        // /23 : 510 hôtes utiles, dont ceux de 192.168.0.x invisibles avant.
        let wide = host_range(ip, 23);
        assert_eq!(wide.len(), 509);
        assert!(wide.contains(&Ipv4Addr::new(192, 168, 0, 1)));
        assert!(!wide.contains(&ip));
        // /16 : ramené au bloc /22 (1022 hôtes) qui contient l'IP.
        let capped = host_range(Ipv4Addr::new(10, 0, 5, 9), 16);
        assert_eq!(capped.len(), 1021);
        assert!(capped.contains(&Ipv4Addr::new(10, 0, 4, 1)));
        assert!(capped.contains(&Ipv4Addr::new(10, 0, 7, 254)));
        assert!(!capped.contains(&Ipv4Addr::new(10, 0, 8, 1)));
        // Liaison point à point : rien à balayer.
        assert!(host_range(ip, 31).is_empty());
        assert!(host_range(ip, 32).is_empty());
    }

    #[test]
    fn prefix_is_derived_from_netmask() {
        assert_eq!(prefix_from_netmask(Ipv4Addr::new(255, 255, 255, 0)), 24);
        assert_eq!(prefix_from_netmask(Ipv4Addr::new(255, 255, 254, 0)), 23);
        assert_eq!(prefix_from_netmask(Ipv4Addr::new(255, 255, 0, 0)), 16);
    }

    #[test]
    fn network_spec_accepts_ip_or_cidr() {
        assert_eq!(parse_network_spec("192.168.2.10"), Some((Ipv4Addr::new(192, 168, 2, 10), 24)));
        assert_eq!(parse_network_spec(" 10.1.0.0/22 "), Some((Ipv4Addr::new(10, 1, 0, 0), 22)));
        assert_eq!(parse_network_spec("10.1.0.0/40"), None);
        assert_eq!(parse_network_spec("bobine.local"), None);
    }

    #[test]
    fn interfaces_are_classified() {
        assert!(!is_scannable_ipv4(Ipv4Addr::new(169, 254, 3, 4)));
        assert!(!is_scannable_ipv4(Ipv4Addr::new(127, 0, 0, 1)));
        assert!(is_scannable_ipv4(Ipv4Addr::new(192, 168, 1, 2)));
        assert!(is_virtual_interface("docker0"));
        assert!(is_virtual_interface("br-3f2a1b"));
        assert!(!is_virtual_interface("wlp3s0"));
        assert!(is_tunnel_interface("tun0", Ipv4Addr::new(10, 8, 0, 2)));
        assert!(is_tunnel_interface("eth9", Ipv4Addr::new(100, 101, 2, 3))); // CGNAT
        assert!(!is_tunnel_interface("en0", Ipv4Addr::new(192, 168, 1, 2)));
    }

    #[test]
    fn linux_arp_table_keeps_only_complete_entries() {
        let table = "IP address       HW type     Flags       HW address            Mask     Device\n\
                     192.168.1.1      0x1         0x2         AA:BB:CC:00:11:22     *        wlp3s0\n\
                     192.168.1.9      0x1         0x0         00:00:00:00:00:00     *        wlp3s0\n\
                     192.168.1.30     0x1         0x2         dc:a6:32:01:02:03     *        wlp3s0\n";
        assert_eq!(
            parse_proc_net_arp(table),
            vec![
                (Ipv4Addr::new(192, 168, 1, 1), "aa:bb:cc:00:11:22".to_string()),
                (Ipv4Addr::new(192, 168, 1, 30), "dc:a6:32:01:02:03".to_string()),
            ]
        );
    }

    #[test]
    fn arp_a_output_is_parsed_for_macos_and_windows() {
        let macos = "? (192.168.1.5) at a4:83:e7:1:2:3 on en0 ifscope [ethernet]\n\
                     ? (192.168.1.77) at (incomplete) on en0 ifscope [ethernet]\n\
                     ? (192.168.1.255) at ff:ff:ff:ff:ff:ff on en0 ifscope [ethernet]\n";
        assert_eq!(
            parse_arp_a(macos),
            vec![(Ipv4Addr::new(192, 168, 1, 5), "a4:83:e7:1:2:3".to_string())]
        );
        let windows = "Interface : 192.168.1.20 --- 0x7\n  Adresse Internet      Adresse physique      Type\n  192.168.1.1           aa-bb-cc-00-11-22     dynamique\n  192.168.1.255         ff-ff-ff-ff-ff-ff     statique\n";
        assert_eq!(
            parse_arp_a(windows),
            vec![(Ipv4Addr::new(192, 168, 1, 1), "aa:bb:cc:00:11:22".to_string())]
        );
    }

    #[test]
    fn candidate_builder_infers_os() {
        let c = Candidate::new(Ipv4Addr::new(10, 0, 0, 30))
            .with_ssh_banner("SSH-2.0-OpenSSH_9.2p1 Debian-2");
        assert_eq!(c.os_hint.as_deref(), Some("Debian"));
        assert_eq!(c.ssh_banner.as_deref(), Some("SSH-2.0-OpenSSH_9.2p1 Debian-2"));
    }
}
