//! Windows : `netsh wlan` (Wi-Fi) et PowerShell (audio, Bluetooth, adresse IP). Les valeurs fournies
//! par l'appelant ne sont JAMAIS interpolées dans un script PowerShell : elles passent par la variable
//! d'environnement `BOBINE_ARG` (aucune injection possible). Le module PowerShell optionnel
//! `AudioDeviceCmdlets` (Get-/Set-AudioDevice) permet de choisir la sortie audio et le volume ; sans lui,
//! la liste des sorties est en lecture seule.
//!
//! ATTENTION : NON VALIDÉ sur un PC Windows réel : les analyseurs (`parse.rs`) sont testés sur des sorties
//! représentatives (anglais et français) ; le comportement réel reste à confirmer (lots P0 / P5).

use crate::exec::{run, run_with_env, Output};
use crate::parse;
use crate::protocol::{capabilities_all, Platform, RpcError, RpcResult};
use serde_json::{json, Map, Value};
use std::time::{Duration, Instant};

const SHORT: Duration = Duration::from_secs(15);
const LONG: Duration = Duration::from_secs(45);
const POWERSHELL: &str = "powershell.exe";

pub struct Windows {
    has_audio_cmdlets: bool,
}

fn powershell(script: &str, arg: Option<&str>, timeout: Duration) -> Result<Output, RpcError> {
    let args = ["-NoProfile", "-NonInteractive", "-Command", script];
    run_with_env(
        POWERSHELL,
        &args,
        timeout,
        None,
        &[("BOBINE_ARG", arg.unwrap_or(""))],
    )
}

fn ok(out: Output, what: &str) -> Result<Output, RpcError> {
    if out.code == 0 {
        Ok(out)
    } else {
        Err(RpcError::app(
            "tool_failed",
            format!("{what} : {}", out.stderr.lines().next().unwrap_or("échec")),
        ))
    }
}

fn prefix_to_mask(prefix: u32) -> String {
    let bits: u32 = if prefix == 0 {
        0
    } else {
        u32::MAX << (32 - prefix.min(32))
    };
    let b = bits.to_be_bytes();
    format!("{}.{}.{}.{}", b[0], b[1], b[2], b[3])
}

impl Windows {
    pub fn new() -> Self {
        let has = powershell(
            "if (Get-Module -ListAvailable -Name AudioDeviceCmdlets) { 'yes' }",
            None,
            SHORT,
        )
        .map(|o| o.stdout.trim() == "yes")
        .unwrap_or(false);
        Windows {
            has_audio_cmdlets: has,
        }
    }

    fn interface(&self) -> Result<parse::NetshInterface, RpcError> {
        let out = ok(
            run("netsh", &["wlan", "show", "interfaces"], SHORT, None)?,
            "netsh",
        )?;
        parse::windows_interface(&out.stdout)
            .ok_or_else(|| RpcError::unsupported("Aucun adaptateur Wi-Fi détecté."))
    }

    fn profiles(&self) -> Vec<String> {
        run("netsh", &["wlan", "show", "profiles"], SHORT, None)
            .map(|o| parse::windows_profiles(&o.stdout))
            .unwrap_or_default()
    }

    fn audio_list(&self) -> RpcResult {
        if self.has_audio_cmdlets {
            let out = ok(powershell(
                "Get-AudioDevice -List | Where-Object { $_.Type -eq 'Playback' } | Select-Object Default,Name,ID | ConvertTo-Json -Compress",
                None, SHORT)?, "PowerShell")?;
            let mut devices = Vec::new();
            let mut default_id = None;
            for item in parse::powershell_json_array(&out.stdout) {
                let id = item["ID"].as_str().unwrap_or("").to_string();
                let name = item["Name"].as_str().unwrap_or("").to_string();
                if id.is_empty() {
                    continue;
                }
                let is_default = item["Default"] == true;
                if is_default {
                    default_id = Some(id.clone());
                }
                let lowered = name.to_lowercase();
                let kind = if lowered.contains("bluetooth") {
                    "bluetooth"
                } else if lowered.contains("hdmi")
                    || lowered.contains("nvidia")
                    || lowered.contains("display")
                {
                    "hdmi"
                } else if lowered.contains("usb") {
                    "usb"
                } else {
                    "other"
                };
                devices.push(json!({ "id": id, "name": name, "description": "", "manufacturer": "", "kind": kind,
                    "is_default": is_default, "available": true, "volume": null, "muted": null }));
            }
            if let Ok(v) = powershell("Get-AudioDevice -PlaybackVolume", None, SHORT) {
                if let Ok(percent) = v
                    .stdout
                    .trim()
                    .trim_end_matches('%')
                    .replace(',', ".")
                    .parse::<f64>()
                {
                    for d in devices.iter_mut().filter(|d| d["is_default"] == true) {
                        d["volume"] = json!(percent / 100.0);
                    }
                }
            }
            return Ok(json!({ "supported": true, "devices": devices, "default_id": default_id }));
        }
        let out = ok(powershell("Get-CimInstance Win32_SoundDevice | Select-Object Name,Manufacturer,Status | ConvertTo-Json -Compress", None, SHORT)?, "PowerShell")?;
        let devices: Vec<Value> = parse::powershell_json_array(&out.stdout)
            .into_iter()
            .map(|i| {
                let name = i["Name"].as_str().unwrap_or("").to_string();
                json!({ "id": name, "name": name, "description": "", "manufacturer": i["Manufacturer"].as_str().unwrap_or(""),
                    "kind": "other", "is_default": false, "available": i["Status"] == "OK", "volume": null, "muted": null })
            })
            .collect();
        Ok(json!({ "supported": true, "devices": devices, "default_id": null }))
    }

    fn wait_connected(&self, ssid: &str, deadline: Duration) -> bool {
        let started = Instant::now();
        while started.elapsed() < deadline {
            if let Ok(i) = self.interface() {
                if i.connected && i.ssid.as_deref() == Some(ssid) {
                    return true;
                }
            }
            std::thread::sleep(Duration::from_millis(1000));
        }
        false
    }
}

impl Platform for Windows {
    fn name(&self) -> &'static str {
        "windows"
    }

    fn capabilities(&self) -> Value {
        let mut caps = capabilities_all(true, "");
        let mut deny = |keys: &[&str], reason: &str| {
            for key in keys {
                caps[*key] = json!({ "supported": false, "reason": reason });
            }
        };
        if !self.has_audio_cmdlets {
            deny(&["audio_set_default", "audio_set_volume"],
                "Installez le module PowerShell AudioDeviceCmdlets (Install-Module AudioDeviceCmdlets) pour choisir la sortie audio.");
        }
        deny(
            &[
                "bluetooth_power",
                "bluetooth_scan",
                "bluetooth_pair",
                "bluetooth_connect",
                "bluetooth_forget",
            ],
            "Sous Windows, l'appairage Bluetooth se fait dans Paramètres > Bluetooth et appareils.",
        );
        deny(
            &["wifi_power"],
            "Activer ou couper la carte Wi-Fi demande des droits d'administrateur sous Windows.",
        );
        caps
    }

    fn call(&self, method: &str, params: &Map<String, Value>) -> RpcResult {
        let s = |k: &str| params.get(k).and_then(Value::as_str).unwrap_or("");
        match method {
            "audio.list" => self.audio_list(),
            "audio.set_default" if self.has_audio_cmdlets => {
                ok(
                    powershell(
                        "Set-AudioDevice -ID $env:BOBINE_ARG | Out-Null",
                        Some(s("id")),
                        SHORT,
                    )?,
                    "PowerShell",
                )?;
                Ok(Value::Null)
            }
            "audio.set_volume" if self.has_audio_cmdlets => {
                if let Some(v) = params.get("volume").and_then(Value::as_f64) {
                    let percent = ((v.clamp(0.0, 1.0)) * 100.0).round() as i64;
                    ok(
                        powershell(
                            "Set-AudioDevice -PlaybackVolume ([int]$env:BOBINE_ARG)",
                            Some(&percent.to_string()),
                            SHORT,
                        )?,
                        "PowerShell",
                    )?;
                }
                if let Some(m) = params.get("muted").and_then(Value::as_bool) {
                    ok(
                        powershell(
                            "Set-AudioDevice -PlaybackMute ($env:BOBINE_ARG -eq 'true')",
                            Some(if m { "true" } else { "false" }),
                            SHORT,
                        )?,
                        "PowerShell",
                    )?;
                }
                Ok(Value::Null)
            }
            "bluetooth.status" => {
                let out = ok(powershell("Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Compress", None, SHORT)?, "PowerShell")?;
                let devices = parse::windows_bluetooth(&parse::powershell_json_array(&out.stdout));
                Ok(
                    json!({ "supported": true, "powered": true, "discovering": false, "adapter_name": "", "devices": devices,
                    "pending_pairing": null, "pairing": null }),
                )
            }
            "wifi.status" => {
                let iface = self.interface()?;
                let known = self.profiles();
                let out = run(
                    "netsh",
                    &["wlan", "show", "networks", "mode=bssid"],
                    LONG,
                    None,
                )?;
                let networks = parse::windows_networks(
                    &out.stdout,
                    iface.ssid.as_deref().filter(|_| iface.connected),
                    &known,
                );
                let current = networks.iter().find(|n| n["in_use"] == true).cloned()
                    .or_else(|| iface.ssid.clone().filter(|_| iface.connected).map(|ssid| json!({
                        "ssid": ssid, "signal": iface.signal, "security": "", "band": iface.band, "known": true, "in_use": true })));
                Ok(json!({
                    "supported": true, "enabled": true, "interface": iface.name,
                    "state": if iface.connected { "connected" } else { "disconnected" },
                    "current": current, "networks": networks, "known": known,
                }))
            }
            "wifi.scan" => Ok(Value::Null), // `show networks` déclenche déjà un balayage récent
            "wifi.current_connection" => {
                let iface = self.interface()?;
                Ok(json!(iface.ssid.filter(|_| iface.connected)))
            }
            "wifi.connect" | "wifi.activate" => {
                let ssid = if method == "wifi.connect" {
                    s("ssid")
                } else {
                    s("connection")
                };
                let password = params
                    .get("password")
                    .and_then(Value::as_str)
                    .filter(|p| !p.is_empty());
                let existed = self.profiles().iter().any(|p| p == ssid);
                let mut created = false;
                if password.is_some() || !existed {
                    // Profil minimal généré dans un fichier temporaire, supprimé aussitôt après l'import.
                    let path = std::env::temp_dir()
                        .join(format!("bobine-wifi-{}.xml", std::process::id()));
                    let path_text = path.to_string_lossy().to_string();
                    std::fs::write(&path, parse::windows_profile_xml(ssid, password)).map_err(
                        |e| RpcError::app("tool_failed", format!("Profil Wi-Fi non écrit : {e}")),
                    )?;
                    let added = run(
                        "netsh",
                        &[
                            "wlan",
                            "add",
                            "profile",
                            &format!("filename={path_text}"),
                            "user=current",
                        ],
                        SHORT,
                        None,
                    );
                    let _ = std::fs::remove_file(&path);
                    ok(added?, "netsh")?;
                    created = !existed;
                }
                let name_arg = format!("name={ssid}");
                ok(
                    run("netsh", &["wlan", "connect", &name_arg], SHORT, None)?,
                    "netsh",
                )?;
                if !self.wait_connected(ssid, Duration::from_secs(25)) {
                    if created {
                        let _ = run(
                            "netsh",
                            &["wlan", "delete", "profile", &name_arg],
                            SHORT,
                            None,
                        ); // ne garde pas un mauvais mot de passe
                    }
                    return Err(RpcError::app(
                        "wifi_auth_failed",
                        "Mot de passe incorrect ou réseau inaccessible.",
                    ));
                }
                Ok(Value::Null)
            }
            "wifi.forget" => {
                let name_arg = format!("name={}", s("ssid"));
                ok(
                    run(
                        "netsh",
                        &["wlan", "delete", "profile", &name_arg],
                        SHORT,
                        None,
                    )?,
                    "netsh",
                )?;
                Ok(Value::Null)
            }
            "wifi.subnet" => {
                let iface = self.interface()?;
                let out = powershell(
                    "Get-NetIPAddress -InterfaceAlias $env:BOBINE_ARG -AddressFamily IPv4 | Select-Object -First 1 IPAddress,PrefixLength | ConvertTo-Json -Compress",
                    Some(&iface.name), SHORT)?;
                let item = parse::powershell_json_array(&out.stdout).into_iter().next();
                Ok(json!(item.and_then(|i| {
                    let prefix = i["PrefixLength"].as_u64()? as u32;
                    parse::subnet_cidr(i["IPAddress"].as_str()?, &prefix_to_mask(prefix))
                })))
            }
            _ => Err(RpcError::unsupported(
                "Méthode non prise en charge sur Windows.",
            )),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prefix_masks() {
        assert_eq!(prefix_to_mask(24), "255.255.255.0");
        assert_eq!(prefix_to_mask(16), "255.255.0.0");
        assert_eq!(prefix_to_mask(0), "0.0.0.0");
        assert_eq!(prefix_to_mask(32), "255.255.255.255");
    }
}
