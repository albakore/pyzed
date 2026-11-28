//! Systems without native notifications (Android for now): Python falls back to its own way.

use super::{Sink, Spec};

pub(super) fn show(_id: u64, _spec: Spec, _sink: Sink) -> Result<(), String> {
    Err("this system has no desktop notifications".into())
}

pub(super) fn close(_id: u64) {}

pub(super) fn supported() -> bool {
    false
}

pub(super) fn capabilities() -> Vec<String> {
    Vec::new()
}
