use crate::exec::{require_success as ok, run_with_env, Output};
use crate::parse;
use crate::protocol::{capabilities_all, Platform, RpcError, RpcResult};
use serde_json::{json, Map, Value};
use std::time::Duration;

const SHORT: Duration = Duration::from_secs(15);
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

fn device_kind(name: &str) -> &'static str {
    let lowered = name.to_lowercase();
    if lowered.contains("bluetooth") {
        "bluetooth"
    } else if lowered.contains("hdmi") || lowered.contains("nvidia") || lowered.contains("display") {
        "hdmi"
    } else if lowered.contains("usb") {
        "usb"
    } else {
        "other"
    }
}

fn playback_devices(stdout: &str) -> (Vec<Value>, Option<String>) {
    let mut devices = Vec::new();
    let mut default_id = None;
    for item in parse::windows::powershell_json_array(stdout) {
        let id = item["ID"].as_str().unwrap_or("").to_string();
        let name = item["Name"].as_str().unwrap_or("").to_string();
        if id.is_empty() {
            continue;
        }
        let is_default = item["Default"] == true;
        if is_default {
            default_id = Some(id.clone());
        }
        devices.push(json!({ "id": id, "name": name, "description": "", "manufacturer": "", "kind": device_kind(&name),
            "is_default": is_default, "available": true, "volume": null, "muted": null }));
    }
    (devices, default_id)
}

fn audio_list_cmdlets() -> RpcResult {
    let out = ok(powershell(
        "Get-AudioDevice -List | Where-Object { $_.Type -eq 'Playback' } | Select-Object Default,Name,ID | ConvertTo-Json -Compress",
        None, SHORT)?, "PowerShell")?;
    let (mut devices, default_id) = playback_devices(&out.stdout);
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
    Ok(json!({ "supported": true, "devices": devices, "default_id": default_id }))
}

fn powershell_null(script: &str, arg: &str) -> RpcResult {
    ok(powershell(script, Some(arg), SHORT)?, "PowerShell")?;
    Ok(Value::Null)
}

fn audio_set_volume(params: &Map<String, Value>) -> RpcResult {
    if let Some(v) = params.get("volume").and_then(Value::as_f64) {
        let percent = ((v.clamp(0.0, 1.0)) * 100.0).round() as i64;
        powershell_null(
            "Set-AudioDevice -PlaybackVolume ([int]$env:BOBINE_ARG)",
            &percent.to_string(),
        )?;
    }
    if let Some(m) = params.get("muted").and_then(Value::as_bool) {
        powershell_null(
            "Set-AudioDevice -PlaybackMute ($env:BOBINE_ARG -eq 'true')",
            if m { "true" } else { "false" },
        )?;
    }
    Ok(Value::Null)
}

fn bluetooth_status() -> RpcResult {
    let out = ok(powershell("Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Compress", None, SHORT)?, "PowerShell")?;
    let devices = parse::windows::bluetooth(&parse::windows::powershell_json_array(&out.stdout));
    Ok(
        json!({ "supported": true, "powered": true, "discovering": false, "adapter_name": "", "devices": devices,
        "pending_pairing": null, "pairing": null }),
    )
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

    fn audio_list(&self) -> RpcResult {
        if self.has_audio_cmdlets {
            return audio_list_cmdlets();
        }
        let out = ok(powershell("Get-CimInstance Win32_SoundDevice | Select-Object Name,Manufacturer,Status | ConvertTo-Json -Compress", None, SHORT)?, "PowerShell")?;
        let devices: Vec<Value> = parse::windows::powershell_json_array(&out.stdout)
            .into_iter()
            .map(|i| {
                let name = i["Name"].as_str().unwrap_or("").to_string();
                json!({ "id": name, "name": name, "description": "", "manufacturer": i["Manufacturer"].as_str().unwrap_or(""),
                    "kind": "other", "is_default": false, "available": i["Status"] == "OK", "volume": null, "muted": null })
            })
            .collect();
        Ok(json!({ "supported": true, "devices": devices, "default_id": null }))
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
        caps
    }

    fn call(&self, method: &str, params: &Map<String, Value>) -> RpcResult {
        let s = |k: &str| params.get(k).and_then(Value::as_str).unwrap_or("");
        match method {
            "audio.list" => self.audio_list(),
            "audio.set_default" if self.has_audio_cmdlets => {
                powershell_null("Set-AudioDevice -ID $env:BOBINE_ARG | Out-Null", s("id"))
            }
            "audio.set_volume" if self.has_audio_cmdlets => audio_set_volume(params),
            "bluetooth.status" => bluetooth_status(),
            _ => Err(RpcError::unsupported(
                "Méthode non prise en charge sur Windows.",
            )),
        }
    }
}
