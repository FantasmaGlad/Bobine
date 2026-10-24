//! macOS : `system_profiler` (lecture), `networksetup` (Wi-Fi), `osascript` (volume) ; outils tiers
//! optionnels détectés au démarrage : `SwitchAudioSource` (sortie audio par défaut) et `blueutil`
//! (pilotage Bluetooth). Sans eux, l'audio par défaut et le Bluetooth restent en lecture seule.
//!
//! ATTENTION : NON VALIDÉ sur un Mac réel : les analyseurs (`parse.rs`) sont testés sur des sorties
//! représentatives ; le comportement réel reste à confirmer (lot P0 / P5 du cahier des charges).

use crate::exec::{run, tool_exists, Output};
use crate::parse;
use crate::protocol::{capabilities_all, Platform, RpcError, RpcResult};
use serde_json::{json, Map, Value};
use std::sync::Mutex;
use std::time::Duration;

const SHORT: Duration = Duration::from_secs(10);
const LONG: Duration = Duration::from_secs(40);

pub struct MacOs {
    has_switch_audio: bool,
    has_blueutil: bool,
    /// Appareils trouvés par le dernier scan Bluetooth (le processus est durable : on les garde en mémoire).
    discovered: Mutex<Vec<Value>>,
}

impl MacOs {
    pub fn new() -> Self {
        MacOs {
            has_switch_audio: tool_exists("SwitchAudioSource"),
            has_blueutil: tool_exists("blueutil"),
            discovered: Mutex::new(Vec::new()),
        }
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

    fn wifi_device(&self) -> Result<String, RpcError> {
        let out = Self::ok(
            run("networksetup", &["-listallhardwareports"], SHORT, None)?,
            "networksetup",
        )?;
        parse::macos_wifi_device(&out.stdout)
            .ok_or_else(|| RpcError::unsupported("Aucun adaptateur Wi-Fi détecté."))
    }

    fn preferred(&self, device: &str) -> Vec<String> {
        run(
            "networksetup",
            &["-listpreferredwirelessnetworks", device],
            SHORT,
            None,
        )
        .map(|o| parse::macos_preferred_networks(&o.stdout))
        .unwrap_or_default()
    }

    fn audio_list(&self) -> RpcResult {
        let out = Self::ok(
            run("system_profiler", &["SPAudioDataType", "-json"], LONG, None)?,
            "system_profiler",
        )?;
        let (mut devices, default_id) = parse::macos_audio(&out.stdout)
            .ok_or_else(|| RpcError::app("parse_failed", "Réponse system_profiler illisible."))?;
        // Volume : uniquement celui de la sortie par défaut (osascript ne sait pas lire les autres).
        if let Ok(v) = run(
            "osascript",
            &["-e", "output volume of (get volume settings)"],
            SHORT,
            None,
        ) {
            if let Ok(percent) = v.stdout.trim().parse::<f64>() {
                for d in devices.iter_mut().filter(|d| d["is_default"] == true) {
                    d["volume"] = json!(percent / 100.0);
                }
            }
        }
        Ok(json!({ "supported": true, "devices": devices, "default_id": default_id }))
    }

    fn bluetooth_status(&self) -> RpcResult {
        let out = Self::ok(
            run(
                "system_profiler",
                &["SPBluetoothDataType", "-json"],
                LONG,
                None,
            )?,
            "system_profiler",
        )?;
        let (powered, mut devices) = parse::macos_bluetooth(&out.stdout)
            .ok_or_else(|| RpcError::app("parse_failed", "Réponse system_profiler illisible."))?;
        if let Ok(found) = self.discovered.lock() {
            for d in found.iter() {
                if !devices.iter().any(|x| x["address"] == d["address"]) {
                    devices.push(d.clone());
                }
            }
        }
        Ok(json!({
            "supported": true,
            "powered": powered,
            "discovering": false,
            "adapter_name": "",
            "devices": devices,
            "pending_pairing": null,
            "pairing": null,
        }))
    }

    fn blueutil(&self, args: &[&str], timeout: Duration) -> Result<Output, RpcError> {
        if !self.has_blueutil {
            return Err(RpcError::unsupported("Installez blueutil (brew install blueutil) pour piloter le Bluetooth depuis Bobine."));
        }
        Self::ok(run("blueutil", args, timeout, None)?, "blueutil")
    }
}

impl Platform for MacOs {
    fn name(&self) -> &'static str {
        "macos"
    }

    fn capabilities(&self) -> Value {
        let mut caps = capabilities_all(true, "");
        let note = |caps: &mut Value, key: &str, reason: &str| {
            caps[key] = json!({ "supported": false, "reason": reason });
        };
        if !self.has_switch_audio {
            note(&mut caps, "audio_set_default", "Installez SwitchAudioSource (brew install switchaudio-osx) pour changer de sortie audio.");
        }
        note_if(
            &mut caps,
            !self.has_blueutil,
            &[
                "bluetooth_power",
                "bluetooth_scan",
                "bluetooth_pair",
                "bluetooth_connect",
                "bluetooth_forget",
            ],
            "Installez blueutil (brew install blueutil) pour piloter le Bluetooth depuis Bobine.",
        );
        caps
    }

    fn call(&self, method: &str, params: &Map<String, Value>) -> RpcResult {
        let s = |k: &str| params.get(k).and_then(Value::as_str).unwrap_or("");
        let b = |k: &str| params.get(k).and_then(Value::as_bool).unwrap_or(false);
        match method {
            "audio.list" => self.audio_list(),
            "audio.set_default" => {
                if !self.has_switch_audio {
                    return Err(RpcError::unsupported(
                        "SwitchAudioSource n'est pas installé.",
                    ));
                }
                Self::ok(
                    run(
                        "SwitchAudioSource",
                        &["-t", "output", "-s", s("id")],
                        SHORT,
                        None,
                    )?,
                    "SwitchAudioSource",
                )?;
                Ok(Value::Null)
            }
            "audio.set_volume" => {
                if let Some(v) = params.get("volume").and_then(Value::as_f64) {
                    let script = format!(
                        "set volume output volume {}",
                        (v.clamp(0.0, 1.0) * 100.0).round() as i64
                    );
                    Self::ok(
                        run("osascript", &["-e", &script], SHORT, None)?,
                        "osascript",
                    )?;
                }
                if let Some(m) = params.get("muted").and_then(Value::as_bool) {
                    let script = format!(
                        "set volume output muted {}",
                        if m { "true" } else { "false" }
                    );
                    Self::ok(
                        run("osascript", &["-e", &script], SHORT, None)?,
                        "osascript",
                    )?;
                }
                Ok(Value::Null)
            }
            "bluetooth.status" => self.bluetooth_status(),
            "bluetooth.set_power" => self
                .blueutil(&["--power", if b("on") { "1" } else { "0" }], SHORT)
                .map(|_| Value::Null),
            "bluetooth.scan" => {
                if !b("on") {
                    return Ok(Value::Null);
                }
                let out = self.blueutil(
                    &["--format", "json", "--inquiry", "6"],
                    Duration::from_secs(30),
                )?;
                let found: Vec<Value> = serde_json::from_str::<Vec<Value>>(&out.stdout)
                    .unwrap_or_default()
                    .into_iter()
                    .map(|d| json!({
                        "address": d["address"].as_str().unwrap_or("").replace('-', ":").to_uppercase(),
                        "name": d["name"].as_str().unwrap_or(d["address"].as_str().unwrap_or("")),
                        "paired": d["paired"].as_bool().unwrap_or(false),
                        "connected": d["connected"].as_bool().unwrap_or(false),
                        "trusted": false, "rssi": d["rawRSSI"], "kind": "other", "profiles": [], "battery": null,
                    }))
                    .collect();
                if let Ok(mut slot) = self.discovered.lock() {
                    *slot = found;
                }
                Ok(Value::Null)
            }
            "bluetooth.pair" => self
                .blueutil(&["--pair", s("address")], Duration::from_secs(45))
                .map(|_| Value::Null),
            "bluetooth.connect" => self
                .blueutil(&["--connect", s("address")], Duration::from_secs(30))
                .map(|_| Value::Null),
            "bluetooth.disconnect" => self
                .blueutil(&["--disconnect", s("address")], SHORT)
                .map(|_| Value::Null),
            "bluetooth.forget" => self
                .blueutil(&["--unpair", s("address")], SHORT)
                .map(|_| Value::Null),
            "wifi.status" => {
                let device = self.wifi_device()?;
                let power_text =
                    run("networksetup", &["-getairportpower", &device], SHORT, None)?.stdout;
                let enabled = parse::macos_wifi_power(&power_text).unwrap_or(true);
                let known = self.preferred(&device);
                let mut networks = Vec::new();
                if enabled {
                    let out = run(
                        "system_profiler",
                        &["SPAirPortDataType", "-json"],
                        LONG,
                        None,
                    )?;
                    networks =
                        parse::macos_airport(&out.stdout, &device, &known).unwrap_or_default();
                }
                let current = networks.iter().find(|n| n["in_use"] == true).cloned();
                Ok(json!({
                    "supported": true,
                    "enabled": enabled,
                    "interface": device,
                    "state": if current.is_some() { "connected" } else { "disconnected" },
                    "current": current,
                    "networks": networks,
                    "known": known,
                }))
            }
            "wifi.scan" => Ok(Value::Null), // la lecture de `wifi.status` déclenche déjà un balayage
            "wifi.set_power" => {
                let device = self.wifi_device()?;
                Self::ok(
                    run(
                        "networksetup",
                        &[
                            "-setairportpower",
                            &device,
                            if b("on") { "on" } else { "off" },
                        ],
                        SHORT,
                        None,
                    )?,
                    "networksetup",
                )?;
                Ok(Value::Null)
            }
            "wifi.current_connection" => {
                let device = self.wifi_device()?;
                let out = run(
                    "networksetup",
                    &["-getairportnetwork", &device],
                    SHORT,
                    None,
                )?;
                Ok(json!(parse::macos_current_network(&out.stdout)))
            }
            "wifi.connect" => {
                let device = self.wifi_device()?;
                let mut args = vec!["-setairportnetwork", device.as_str(), s("ssid")];
                // ATTENTION : networksetup n'accepte le mot de passe qu'en argument (visible brièvement dans `ps`,
                // sur cette machine seulement) ; il n'existe pas d'entrée standard équivalente.
                if let Some(pw) = params
                    .get("password")
                    .and_then(Value::as_str)
                    .filter(|p| !p.is_empty())
                {
                    args.push(pw);
                }
                let out = run("networksetup", &args, Duration::from_secs(45), None)?;
                // networksetup renvoie 0 même en cas d'échec : l'erreur est dans la sortie.
                let text = format!("{}{}", out.stdout, out.stderr);
                if text.contains("Failed to join")
                    || text.contains("Could not find network")
                    || text.contains("Error")
                {
                    return Err(RpcError::app(
                        "wifi_auth_failed",
                        "Mot de passe incorrect ou réseau inaccessible.",
                    ));
                }
                Ok(Value::Null)
            }
            "wifi.activate" => {
                let device = self.wifi_device()?;
                Self::ok(
                    run(
                        "networksetup",
                        &["-setairportnetwork", &device, s("connection")],
                        Duration::from_secs(45),
                        None,
                    )?,
                    "networksetup",
                )?;
                Ok(Value::Null)
            }
            "wifi.forget" => {
                let device = self.wifi_device()?;
                Self::ok(
                    run(
                        "networksetup",
                        &["-removepreferredwirelessnetwork", &device, s("ssid")],
                        SHORT,
                        None,
                    )?,
                    "networksetup",
                )?;
                Ok(Value::Null)
            }
            "wifi.subnet" => {
                let device = self.wifi_device()?;
                let ip = run("ipconfig", &["getifaddr", &device], SHORT, None)?.stdout;
                let ifconfig = run("ifconfig", &[&device], SHORT, None)?.stdout;
                let mask = ifconfig
                    .split_whitespace()
                    .skip_while(|w| *w != "netmask")
                    .nth(1)
                    .unwrap_or("");
                Ok(json!(parse::subnet_cidr(ip.trim(), mask)))
            }
            _ => Err(RpcError::unsupported(
                "Méthode non prise en charge sur macOS.",
            )),
        }
    }
}

fn note_if(caps: &mut Value, condition: bool, keys: &[&str], reason: &str) {
    if condition {
        for key in keys {
            caps[*key] = json!({ "supported": false, "reason": reason });
        }
    }
}
