//! Stands in for `device.rs` in a Linux build from source without ALSA's development files:
//! the engine still renders offline and on the silent clock, and says how to get sound.

use std::sync::{Arc, Mutex};

use super::backend::{DeviceInfo, Live, Meters, Opened, Request};
use super::graph::Graph;

pub const MISSING: &str = "this build of Pyzed has no audio devices: it was compiled without ALSA. \
Install libasound2-dev and pkg-config (Fedora: alsa-lib-devel), then rebuild with \
`maturin develop --release --features alsa`";

pub fn host_names() -> Vec<String> {
    vec!["null".into()]
}

pub fn default_host_name() -> String {
    "null".into()
}

pub fn devices(_host: Option<&str>) -> Result<Vec<DeviceInfo>, String> {
    Err(MISSING.into())
}

pub fn open_device(
    _graph: Arc<Mutex<Graph>>,
    _request: Request,
    _meters: Arc<Meters>,
) -> Result<(Live, Opened), String> {
    Err(format!("no audio output device: {MISSING}"))
}
