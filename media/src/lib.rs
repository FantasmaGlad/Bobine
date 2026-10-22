//! Experimental, read-only media inspection over bounded JSON-RPC lines.
mod aiff;
mod audio;
mod flac;
mod image;
mod mp3;
mod mp4;
mod ogg;
mod vorbis;
mod wav;

use serde::Deserialize;
use serde_json::{json, value::RawValue, Value};
use std::io::{self, BufRead, Write};

pub const REQUEST_BYTES: usize = 64 * 1024;
pub const RESPONSE_BYTES: usize = 8 * 1024 * 1024;
pub const COVER_BYTES: usize = 4 * 1024 * 1024;
const MAX_ID: u64 = (1_u64 << 53) - 1;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    jsonrpc: String,
    id: u64,
    method: String,
    #[serde(default = "empty_params")]
    params: Box<RawValue>,
}

fn empty_params() -> Box<RawValue> {
    RawValue::from_string("{}".to_owned()).expect("static JSON object")
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Empty {}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct AudioParams {
    path: String,
    profile: String,
}

#[derive(Debug)]
pub(crate) struct MediaError {
    reason: &'static str,
    message: &'static str,
}

impl MediaError {
    pub(crate) fn new(reason: &'static str, message: &'static str) -> Self {
        Self { reason, message }
    }
}

fn error(id: Value, code: i32, reason: &str, message: &str) -> Value {
    json!({"jsonrpc":"2.0","id":id,"error":{"code":code,"message":message,"data":{"reason":reason}}})
}

/// Dispatch exactly one request. Invalid envelopes never echo untrusted content.
pub fn dispatch(raw: &[u8]) -> Value {
    if raw.len() > REQUEST_BYTES {
        return error(
            Value::Null,
            -32001,
            "limit_exceeded",
            "Request exceeds byte limit",
        );
    }
    let request: Request = match serde_json::from_slice(raw) {
        Ok(request) => request,
        Err(_) => {
            let (code, reason, message) = if serde_json::from_slice::<Value>(raw).is_err() {
                (-32700, "parse_error", "Invalid JSON")
            } else {
                (-32600, "invalid_request", "Invalid request envelope")
            };
            return error(Value::Null, code, reason, message);
        }
    };
    if request.jsonrpc != "2.0" || request.id == 0 || request.id > MAX_ID {
        return error(
            Value::Null,
            -32600,
            "invalid_request",
            "Invalid request envelope",
        );
    }
    let id = json!(request.id);
    let params = request.params.get();
    let result = match request.method.as_str() {
        "hello" => {
            if serde_json::from_str::<Empty>(params).is_err() {
                return error(id, -32602, "invalid_params", "Invalid hello parameters");
            }
            Ok(json!({
                "protocol_version":1,
                "binary_version":env!("CARGO_PKG_VERSION"),
                "profiles":["radio-v1","course-duration-v1"],
                "formats":audio::FORMATS,
                "capabilities":{"probe_audio":true,"extract_cover":true,"experimental":true},
                "limits":{"request_bytes":REQUEST_BYTES,"response_bytes":RESPONSE_BYTES,"cover_bytes":COVER_BYTES}
            }))
        }
        "probe_audio" | "extract_cover" => {
            let params: AudioParams = match serde_json::from_str(params) {
                Ok(params) => params,
                Err(_) => return error(id, -32602, "invalid_params", "Invalid audio parameters"),
            };
            if !matches!(params.profile.as_str(), "radio-v1" | "course-duration-v1") {
                return error(id, -32602, "invalid_params", "Unknown audio profile");
            }
            audio::inspect(
                &params.path,
                &params.profile,
                request.method == "extract_cover",
            )
        }
        _ => return error(id, -32601, "method_not_found", "Unknown method"),
    };
    match result {
        Ok(result) => json!({"jsonrpc":"2.0","id":id,"result":result}),
        Err(failure) => error(id, -32001, failure.reason, failure.message),
    }
}

/// Read at most REQUEST_BYTES + one CR byte; discard oversized frames without growing the buffer.
/// An unterminated final line is processed once; empty EOF stops without output.
pub fn serve<R: BufRead, W: Write>(mut reader: R, mut writer: W) -> io::Result<()> {
    loop {
        let mut line = Vec::with_capacity(1024);
        let mut oversized = false;
        let mut received = false;
        loop {
            let chunk = reader.fill_buf()?;
            if chunk.is_empty() {
                break;
            }
            received = true;
            let newline = chunk.iter().position(|&byte| byte == b'\n');
            let used = newline.map_or(chunk.len(), |pos| pos + 1);
            let payload = if newline.is_some() { used - 1 } else { used };
            if !oversized {
                if line.len().saturating_add(payload) <= REQUEST_BYTES + 1 {
                    line.extend_from_slice(&chunk[..payload]);
                } else {
                    oversized = true;
                    line.clear();
                }
            }
            reader.consume(used);
            if newline.is_some() {
                break;
            }
        }
        if !received {
            return Ok(());
        }
        if line.last() == Some(&b'\r') {
            line.pop();
        }
        let response = if oversized || line.len() > REQUEST_BYTES {
            error(
                Value::Null,
                -32001,
                "limit_exceeded",
                "Request exceeds byte limit",
            )
        } else {
            dispatch(&line)
        };
        let mut encoded = serde_json::to_vec(&response)?;
        if encoded.len() > RESPONSE_BYTES {
            encoded = serde_json::to_vec(&error(
                response["id"].clone(),
                -32001,
                "limit_exceeded",
                "Response exceeds byte limit",
            ))?;
        }
        writer.write_all(&encoded)?;
        writer.write_all(b"\n")?;
        writer.flush()?;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufReader, Cursor};

    fn call(method: &str, params: Value) -> Value {
        dispatch(
            json!({"jsonrpc":"2.0","id":7,"method":method,"params":params})
                .to_string()
                .as_bytes(),
        )
    }

    #[test]
    fn hello_and_unknown_method() {
        let hello = call("hello", json!({}));
        assert_eq!(hello["id"], 7);
        assert_eq!(hello["result"]["protocol_version"], 1);
        assert_eq!(hello["result"]["capabilities"]["experimental"], true);
        assert_eq!(hello["result"]["limits"]["cover_bytes"], COVER_BYTES);
        assert_eq!(call("missing", json!({}))["error"]["code"], -32601);
        assert_eq!(
            call("hello", json!({"extra":true}))["error"]["code"],
            -32602
        );
        assert_eq!(call("hello", Value::Null)["error"]["code"], -32602);
    }

    #[test]
    fn strict_envelopes_and_params() {
        for raw in [
            "{}",
            "[]",
            "null",
            r#"{"jsonrpc":"2.0","id":0,"method":"hello"}"#,
            r#"{"jsonrpc":"2.0","id":true,"method":"hello"}"#,
            r#"{"jsonrpc":"2.0","id":1,"id":2,"method":"hello"}"#,
            r#"{"jsonrpc":"2.0","id":9007199254740992,"method":"hello"}"#,
            r#"{"jsonrpc":"2.0","id":1.0,"method":"hello"}"#,
        ] {
            assert_eq!(dispatch(raw.as_bytes())["error"]["code"], -32600, "{raw}");
        }
        assert_eq!(dispatch(b"{")["error"]["code"], -32700);
        assert_eq!(
            call("probe_audio", json!({"path":"/x","profile":"unknown"}))["error"]["code"],
            -32602
        );
        assert_eq!(dispatch(br#"{"jsonrpc":"2.0","id":1,"method":"probe_audio","params":{"path":"/x","path":"/y","profile":"radio-v1"}}"#)["error"]["code"], -32602);
    }

    #[test]
    fn bounded_line_reader_recovers_after_oversize_and_handles_eof() {
        let mut input = vec![b' '; REQUEST_BYTES * 3];
        input.extend_from_slice(
            b"\n{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"hello\",\"params\":{}}",
        );
        let mut output = Vec::new();
        serve(BufReader::with_capacity(7, Cursor::new(input)), &mut output).unwrap();
        let replies: Vec<Value> = output
            .split(|&b| b == b'\n')
            .filter(|line| !line.is_empty())
            .map(|line| serde_json::from_slice(line).unwrap())
            .collect();
        assert_eq!(replies.len(), 2);
        assert_eq!(replies[0]["error"]["data"]["reason"], "limit_exceeded");
        assert_eq!(replies[1]["result"]["protocol_version"], 1);
        let mut empty = Vec::new();
        serve(Cursor::new([]), &mut empty).unwrap();
        assert!(empty.is_empty());
    }

    #[test]
    fn exact_boundary_and_crlf() {
        let request = br#"{"jsonrpc":"2.0","id":1,"method":"hello"}"#;
        for ending in [b"\n".as_slice(), b"\r\n".as_slice()] {
            let mut input = request.to_vec();
            input.resize(REQUEST_BYTES, b' ');
            input.extend_from_slice(ending);
            let mut output = Vec::new();
            serve(BufReader::with_capacity(5, Cursor::new(input)), &mut output).unwrap();
            assert_eq!(
                serde_json::from_slice::<Value>(&output).unwrap()["result"]["protocol_version"],
                1
            );
        }
        let mut input = request.to_vec();
        input.resize(REQUEST_BYTES + 1, b' ');
        let mut output = Vec::new();
        serve(Cursor::new(input), &mut output).unwrap();
        assert_eq!(
            serde_json::from_slice::<Value>(&output).unwrap()["error"]["data"]["reason"],
            "limit_exceeded"
        );
    }
}
