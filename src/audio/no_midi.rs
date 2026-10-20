//! Stands in for `midi.rs` in a Linux build from source without ALSA's development files.

use std::sync::{Arc, Mutex};

use rtrb::{Consumer, Producer};

use super::device::MISSING;

pub struct InputConnection;

impl InputConnection {
    pub fn close(self) {}
}

pub fn inputs() -> Result<Vec<String>, String> {
    Err(MISSING.into())
}

pub fn outputs() -> Result<Vec<String>, String> {
    Err(MISSING.into())
}

pub fn open_input(
    _name: Option<&str>,
    _virtual_name: Option<&str>,
    _sink: Arc<Mutex<Producer<[u8; 3]>>>,
) -> Result<(InputConnection, String), String> {
    Err(format!("no MIDI: {MISSING}"))
}

pub struct Output {
    pub name: String,
}

impl Output {
    pub fn open(
        _name: Option<&str>,
        _virtual_name: Option<&str>,
        events: Consumer<[u8; 3]>,
    ) -> Result<Self, (String, Consumer<[u8; 3]>)> {
        Err((format!("no MIDI: {MISSING}"), events))
    }

    pub fn send(&self, _msg: &[u8]) -> Result<(), String> {
        Err(MISSING.into())
    }

    pub fn close(self) -> Option<Consumer<[u8; 3]>> {
        None
    }
}
