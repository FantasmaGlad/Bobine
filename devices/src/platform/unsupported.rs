//! Plateformes sans backend (Linux : géré par le backend Python via D-Bus, pas par ce sidecar).

use crate::protocol::{capabilities_all, Platform, RpcError, RpcResult};
use serde_json::{Map, Value};

pub struct Unsupported;

impl Platform for Unsupported {
    fn name(&self) -> &'static str {
        "unsupported"
    }
    fn capabilities(&self) -> Value {
        capabilities_all(
            false,
            "Ce système n'est pas pris en charge par le sidecar de périphériques.",
        )
    }
    fn call(&self, _method: &str, _params: &Map<String, Value>) -> RpcResult {
        Err(RpcError::unsupported(
            "Ce système n'est pas pris en charge par le sidecar de périphériques.",
        ))
    }
}
