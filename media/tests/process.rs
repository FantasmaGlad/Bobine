use serde_json::{json, Value};
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

struct Scratch(PathBuf);
impl Scratch {
    fn new() -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("bobine-media-test-{}-{nonce}", std::process::id()));
        std::fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn pcm() -> Vec<u8> {
    let mut bytes = Vec::new();
    bytes.extend_from_slice(b"RIFF");
    bytes.extend_from_slice(&8040_u32.to_le_bytes());
    bytes.extend_from_slice(b"WAVEfmt ");
    bytes.extend_from_slice(&16_u32.to_le_bytes());
    bytes.extend_from_slice(&1_u16.to_le_bytes());
    bytes.extend_from_slice(&1_u16.to_le_bytes());
    bytes.extend_from_slice(&8000_u32.to_le_bytes());
    bytes.extend_from_slice(&8000_u32.to_le_bytes());
    bytes.extend_from_slice(&1_u16.to_le_bytes());
    bytes.extend_from_slice(&8_u16.to_le_bytes());
    bytes.extend_from_slice(b"data");
    bytes.extend_from_slice(&8004_u32.to_le_bytes());
    bytes.resize(8048, 128);
    bytes
}

fn request(method: &str, path: &str, profile: &str) -> Value {
    bobine_media::dispatch(
        json!({"jsonrpc":"2.0","id":1,"method":method,"params":{"path":path,"profile":profile}})
            .to_string()
            .as_bytes(),
    )
}

#[test]
fn one_process_handles_multiple_requests_and_exits_on_eof() {
    let mut process = Command::new(env!("CARGO_BIN_EXE_bobine-media"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut stdin = process.stdin.take().unwrap();
    stdin.write_all(b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"hello\"}\n{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"unknown\"}\n").unwrap();
    drop(stdin);
    let output = process.wait_with_output().unwrap();
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    let responses: Vec<Value> = output
        .stdout
        .split(|byte| *byte == b'\n')
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_slice(line).unwrap())
        .collect();
    assert_eq!(responses.len(), 2);
    assert_eq!(responses[0]["result"]["protocol_version"], 1);
    assert_eq!(responses[1]["error"]["code"], -32601);
}

#[test]
fn real_pcm_is_read_only_has_exact_duration_and_no_cover() {
    let scratch = Scratch::new();
    let path = scratch.0.join("Été 東京 01.wav");
    let bytes = pcm();
    std::fs::write(&path, &bytes).unwrap();
    for profile in ["radio-v1", "course-duration-v1"] {
        let response = request("probe_audio", path.to_str().unwrap(), profile);
        assert_eq!(response["result"]["format"], "wav", "{response}");
        assert_eq!(response["result"]["profile"], profile);
        assert_eq!(response["result"]["metadata"].as_object().unwrap().len(), 9);
        assert!(response["result"]["metadata"]["title"].is_null());
        let duration = response["result"]["metadata"]["duration_seconds"]
            .as_f64()
            .unwrap();
        assert!((duration - 1.0005).abs() < 0.001);
    }
    let cover = request("extract_cover", path.to_str().unwrap(), "radio-v1");
    assert_eq!(cover["result"], json!({"status":"ok","cover":null}));
    assert_eq!(std::fs::read(&path).unwrap(), bytes);
}

#[test]
fn invalid_media_and_paths_return_sanitized_fallback_errors() {
    let scratch = Scratch::new();
    for (name, bytes, reason) in [
        ("broken.mp3", b"broken".as_slice(), "corrupt"),
        ("other.wma", b"invalid".as_slice(), "unsupported"),
    ] {
        let path = scratch.0.join(name);
        std::fs::write(&path, bytes).unwrap();
        let response = request("probe_audio", path.to_str().unwrap(), "radio-v1");
        assert_eq!(response["error"]["data"]["reason"], reason, "{response}");
        assert!(!response
            .to_string()
            .contains(&scratch.0.to_string_lossy().to_string()));
    }
    let missing = scratch.0.join("missing.mp3");
    assert_eq!(
        request("probe_audio", missing.to_str().unwrap(), "radio-v1")["error"]["data"]["reason"],
        "not_found"
    );
    assert_eq!(
        request("probe_audio", "relative.mp3", "radio-v1")["error"]["data"]["reason"],
        "unsupported"
    );
    assert_eq!(
        request("probe_audio", scratch.0.to_str().unwrap(), "radio-v1")["error"]["data"]["reason"],
        "unsupported"
    );
}

#[test]
fn embedded_cover_requires_reference_pipeline_and_huge_tag_is_rejected() {
    let scratch = Scratch::new();
    let path = scratch.0.join("image.mp3");
    let mut bytes = b"ID3\x04\0\0\0\0\0\x0eAPIC\0\0\0\x04\0\0test\xff\xfb\x90\0".to_vec();
    bytes.resize(80, 0);
    bytes[60..64].copy_from_slice(b"Info");
    std::fs::write(&path, &bytes).unwrap();
    assert_eq!(
        request("extract_cover", path.to_str().unwrap(), "radio-v1")["error"]["data"]["reason"],
        "ambiguous_cover"
    );
    bytes[6..10].copy_from_slice(&[0x7f, 0x7f, 0x7f, 0x7f]);
    std::fs::write(&path, &bytes).unwrap();
    assert_eq!(
        request("probe_audio", path.to_str().unwrap(), "radio-v1")["error"]["data"]["reason"],
        "limit_exceeded"
    );
}
