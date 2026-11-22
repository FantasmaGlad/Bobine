use crate::exec::{require_success, run, tool_exists, Output};
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

    fn audio_list(&self) -> RpcResult {
        let out = require_success(
            run("system_profiler", &["SPAudioDataType", "-json"], LONG, None)?,
            "system_profiler",
        )?;
        let (mut devices, default_id) = parse::macos::audio(&out.stdout)
            .ok_or_else(|| RpcError::app("parse_failed", "Réponse system_profiler illisible."))?;
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
        let out = require_success(
            run(
                "system_profiler",
                &["SPBluetoothDataType", "-json"],
                LONG,
                None,
            )?,
            "system_profiler",
        )?;
        let (powered, mut devices) = parse::macos::bluetooth(&out.stdout)
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
        require_success(run("blueutil", args, timeout, None)?, "blueutil")
    }

    fn audio_set_default(&self, id: &str) -> RpcResult {
        if !self.has_switch_audio {
            return Err(RpcError::unsupported(
                "SwitchAudioSource n'est pas installé.",
            ));
        }
        require_success(
            run(
                "SwitchAudioSource",
                &["-t", "output", "-s", id],
                SHORT,
                None,
            )?,
            "SwitchAudioSource",
        )?;
        Ok(Value::Null)
    }

    fn blueutil_null(&self, args: &[&str], timeout: Duration) -> RpcResult {
        self.blueutil(args, timeout).map(|_| Value::Null)
    }

    fn bluetooth_scan(&self, on: bool) -> RpcResult {
        if !on {
            return Ok(Value::Null);
        }
        let out = self.blueutil(
            &["--format", "json", "--inquiry", "6"],
            Duration::from_secs(30),
        )?;
        let found: Vec<Value> = serde_json::from_str::<Vec<Value>>(&out.stdout)
            .unwrap_or_default()
            .iter()
            .map(discovered_device)
            .collect();
        if let Ok(mut slot) = self.discovered.lock() {
            *slot = found;
        }
        Ok(Value::Null)
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
        let s = |k: &str| str_param(params, k);
        let on = || params.get("on").and_then(Value::as_bool).unwrap_or(false);
        match method {
            "audio.list" => self.audio_list(),
            "audio.set_default" => self.audio_set_default(s("id")),
            "audio.set_volume" => audio_set_volume(params),
            "bluetooth.status" => self.bluetooth_status(),
            "bluetooth.set_power" => self.blueutil_null(&["--power", if on() { "1" } else { "0" }], SHORT),
            "bluetooth.scan" => self.bluetooth_scan(on()),
            "bluetooth.pair" => self.blueutil_null(&["--pair", s("address")], Duration::from_secs(45)),
            "bluetooth.connect" => self.blueutil_null(&["--connect", s("address")], Duration::from_secs(30)),
            "bluetooth.disconnect" => self.blueutil_null(&["--disconnect", s("address")], SHORT),
            "bluetooth.forget" => self.blueutil_null(&["--unpair", s("address")], SHORT),
            _ => Err(RpcError::unsupported(
                "Méthode non prise en charge sur macOS.",
            )),
        }
    }
}

fn str_param<'a>(params: &'a Map<String, Value>, key: &str) -> &'a str {
    params.get(key).and_then(Value::as_str).unwrap_or("")
}

fn osascript(script: &str) -> Result<Output, RpcError> {
    require_success(run("osascript", &["-e", script], SHORT, None)?, "osascript")
}

fn audio_set_volume(params: &Map<String, Value>) -> RpcResult {
    if let Some(v) = params.get("volume").and_then(Value::as_f64) {
        osascript(&format!(
            "set volume output volume {}",
            (v.clamp(0.0, 1.0) * 100.0).round() as i64
        ))?;
    }
    if let Some(m) = params.get("muted").and_then(Value::as_bool) {
        osascript(&format!(
            "set volume output muted {}",
            if m { "true" } else { "false" }
        ))?;
    }
    Ok(Value::Null)
}

fn discovered_device(d: &Value) -> Value {
    json!({
        "address": d["address"].as_str().unwrap_or("").replace('-', ":").to_uppercase(),
        "name": d["name"].as_str().unwrap_or(d["address"].as_str().unwrap_or("")),
        "paired": d["paired"].as_bool().unwrap_or(false),
        "connected": d["connected"].as_bool().unwrap_or(false),
        "trusted": false, "rssi": d["rawRSSI"], "kind": "other", "profiles": [], "battery": null,
    })
}

fn note_if(caps: &mut Value, condition: bool, keys: &[&str], reason: &str) {
    if condition {
        for key in keys {
            caps[*key] = json!({ "supported": false, "reason": reason });
        }
    }
}
