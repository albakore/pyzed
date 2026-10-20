//! Where the sound goes: an audio device through the system's own API (WASAPI or ASIO on
//! Windows, CoreAudio on macOS, PulseAudio/PipeWire or ALSA on Linux), or a clock with no device
//! at all for servers and tests.

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use super::graph::Graph;

/// What `start` asks for. `None` picks what suits the system best.
#[derive(Clone, Default)]
#[cfg_attr(not(audio_devices), allow(dead_code))]
pub struct Request {
    pub host: Option<String>,
    pub device: Option<String>,
    pub input: bool,
    pub input_device: Option<String>,
    pub sample_rate: Option<u32>,
    pub buffer_size: Option<u32>,
}

/// What `start` got.
#[derive(Clone, Default)]
pub struct Opened {
    pub backend: &'static str,
    pub host: String,
    pub device: String,
    pub input_device: Option<String>,
    pub sample_rate: u32,
    /// `None` when the system chose (it did not accept the size asked for).
    pub buffer_size: Option<u32>,
    pub channels: u16,
    pub sample_format: String,
}

/// Measured while playing, read by `engine.info`.
#[derive(Default)]
pub struct Meters {
    /// From the moment the callback runs to the moment its sound plays.
    pub latency_us: AtomicU64,
    /// The share of each buffer's time spent computing it (above 1 the sound breaks up).
    pub load: AtomicU32,
    pub underruns: AtomicU64,
    pub error: Mutex<Option<String>>,
}

pub struct Live {
    pub(super) stop: mpsc::Sender<()>,
    pub(super) handle: Option<JoinHandle<()>>,
}

impl Live {
    pub fn stop(mut self) {
        let _ = self.stop.send(());
        if let Some(handle) = self.handle.take() {
            let _ = handle.join();
        }
    }
}

/// Flushes denormal numbers to zero on the current (audio) thread: decaying reverb tails and
/// filters would otherwise slow the processor down a hundredfold near silence.
pub(super) fn flush_denormals() {
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    #[allow(deprecated)]
    unsafe {
        #[cfg(target_arch = "x86")]
        use std::arch::x86::{_mm_getcsr, _mm_setcsr};
        #[cfg(target_arch = "x86_64")]
        use std::arch::x86_64::{_mm_getcsr, _mm_setcsr};
        _mm_setcsr(_mm_getcsr() | 0x8040);
    }
    #[cfg(target_arch = "aarch64")]
    unsafe {
        let mut fpcr: u64;
        std::arch::asm!("mrs {}, fpcr", out(reg) fpcr);
        std::arch::asm!("msr fpcr, {}", in(reg) fpcr | (1 << 24));
    }
}

/// The buffer that keeps the latency low without dropouts on each system's usual setup.
pub fn recommended_buffer(host: &str) -> Option<u32> {
    match host {
        "CoreAudio" | "ASIO" => Some(128),
        "JACK" => None,
        _ => Some(256),
    }
}

pub struct DeviceInfo {
    pub name: String,
    pub id: String,
    pub host: String,
    pub inputs: u16,
    pub outputs: u16,
    pub sample_rate: Option<u32>,
    pub buffer_range: Option<(u32, u32)>,
    pub default_input: bool,
    pub default_output: bool,
}

/// Runs the graph against the clock alone, `buffer` frames at a time: the backend for machines
/// without sound (servers, CI) and for `backend="null"`.
pub fn open_null(
    graph: Arc<Mutex<Graph>>,
    sr: u32,
    buffer: u32,
    meters: Arc<Meters>,
) -> (Live, Opened) {
    let (stop, stopped) = mpsc::channel::<()>();
    let thread_meters = meters.clone();
    let handle = std::thread::Builder::new()
        .name("pyzed-audio".into())
        .spawn(move || {
            let meters = thread_meters;
            flush_denormals();
            let mut scratch = vec![0.0f32; buffer as usize * 2];
            let period = buffer as f64 / sr as f64;
            // Keep time by the frames rendered, not by the wake-ups: a coarse system timer
            // (Windows, a busy CI machine) wakes late, so each wake renders every block due.
            let max_lag = (sr as u64 / 10).max(buffer as u64);
            let start = Instant::now();
            let mut rendered: u64 = 0;
            loop {
                let due = (start.elapsed().as_secs_f64() * sr as f64) as u64;
                if due > rendered + max_lag {
                    // Fell far behind (the machine stalled): skip ahead instead of bursting.
                    rendered = due - due % buffer as u64;
                }
                while rendered + buffer as u64 <= due {
                    let started = Instant::now();
                    match graph.try_lock() {
                        Ok(mut g) => g.render(&mut scratch, 2),
                        Err(_) => {
                            meters.underruns.fetch_add(1, Ordering::Relaxed);
                        }
                    }
                    let load = started.elapsed().as_secs_f64() / period;
                    meters
                        .load
                        .store((load as f32).to_bits(), Ordering::Relaxed);
                    rendered += buffer as u64;
                }
                let next =
                    start + Duration::from_secs_f64((rendered + buffer as u64) as f64 / sr as f64);
                let wait = next.saturating_duration_since(Instant::now());
                if !matches!(
                    stopped.recv_timeout(wait),
                    Err(mpsc::RecvTimeoutError::Timeout)
                ) {
                    break; // asked to stop, or the engine is gone
                }
            }
        })
        .expect("start the audio thread");
    meters
        .latency_us
        .store((buffer as f64 / sr as f64 * 1e6) as u64, Ordering::Relaxed);
    let opened = Opened {
        backend: "null",
        host: "null".into(),
        device: "none".into(),
        input_device: None,
        sample_rate: sr,
        buffer_size: Some(buffer),
        channels: 2,
        sample_format: "f32".into(),
    };
    (
        Live {
            stop,
            handle: Some(handle),
        },
        opened,
    )
}
