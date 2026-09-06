use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RemoteTarget {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct PlaybackActionRequest {
    pub channel: String,
    #[serde(default)]
    pub volume: Option<f64>,
    #[serde(default)]
    pub position: Option<f64>,
}

#[tauri::command]
pub async fn remote_get_health(target: RemoteTarget) -> Result<serde_json::Value, String> {
    let url = format!("http://{}:{}/api/health", target.host, target.port);
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .map_err(|e| format!("Client HTTP : {e}"))?;

    let res = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("Impossible de joindre Bobine sur {url} : {e}"))?;

    res.json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Réponse JSON invalide : {e}"))
}

#[tauri::command]
pub async fn remote_get_playback(target: RemoteTarget, channel: String) -> Result<serde_json::Value, String> {
    let url = format!("http://{}:{}/api/playback/state?channel={}", target.host, target.port, channel);
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .map_err(|e| format!("Client HTTP : {e}"))?;

    let res = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("Erreur de requête état : {e}"))?;

    res.json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Erreur décodage état : {e}"))
}

#[tauri::command]
pub async fn remote_control_playback(
    target: RemoteTarget,
    action: String,
    channel: String,
    val: Option<f64>,
) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(4))
        .build()
        .map_err(|e| format!("Client HTTP : {e}"))?;

    let base_url = format!("http://{}:{}/api/playback", target.host, target.port);

    match action.as_str() {
        "play" => {
            let res = client
                .post(format!("{base_url}/play"))
                .json(&serde_json::json!({ "channel": channel }))
                .send()
                .await
                .map_err(|e| format!("Erreur action play : {e}"))?;
            res.json::<serde_json::Value>().await.map_err(|e| e.to_string())
        }
        "pause" => {
            let res = client
                .post(format!("{base_url}/pause"))
                .json(&serde_json::json!({ "channel": channel }))
                .send()
                .await
                .map_err(|e| format!("Erreur action pause : {e}"))?;
            res.json::<serde_json::Value>().await.map_err(|e| e.to_string())
        }
        "stop" => {
            let res = client
                .post(format!("{base_url}/stop"))
                .json(&serde_json::json!({ "channel": channel }))
                .send()
                .await
                .map_err(|e| format!("Erreur action stop : {e}"))?;
            res.json::<serde_json::Value>().await.map_err(|e| e.to_string())
        }
        "volume" => {
            let vol = val.unwrap_or(1.0);
            let res = client
                .post(format!("{base_url}/volume"))
                .json(&serde_json::json!({ "channel": channel, "volume": vol }))
                .send()
                .await
                .map_err(|e| format!("Erreur action volume : {e}"))?;
            res.json::<serde_json::Value>().await.map_err(|e| e.to_string())
        }
        "seek" => {
            let pos = val.unwrap_or(0.0);
            let res = client
                .post(format!("{base_url}/seek"))
                .json(&serde_json::json!({ "channel": channel, "position": pos }))
                .send()
                .await
                .map_err(|e| format!("Erreur action seek : {e}"))?;
            res.json::<serde_json::Value>().await.map_err(|e| e.to_string())
        }
        other => Err(format!("Action inconnue '{other}'")),
    }
}
