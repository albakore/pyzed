//! Where the sound goes: an audio device through the system's own API (WASAPI or ASIO on
//! Windows, CoreAudio on macOS, PulseAudio/PipeWire or ALSA on Linux), or a clock with no device
//! at all for servers and tests.

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{BufferSize, FromSample, SampleFormat, SizedSample, StreamConfig, SupportedBufferSize};
use rtrb::RingBuffer;

use super::graph::Graph;

/// What `start` asks for. `None` picks what suits the system best.
#[derive(Clone, Default)]
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
    stop: mpsc::Sender<()>,
    handle: Option<JoinHandle<()>>,
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
fn flush_denormals() {
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

pub fn host_names() -> Vec<String> {
    cpal::available_hosts()
        .into_iter()
        .map(|id| id.name().to_string())
        .collect()
}

pub fn default_host_name() -> String {
    cpal::default_host().id().name().to_string()
}

fn host_by_name(name: Option<&str>) -> Result<cpal::Host, String> {
    let Some(name) = name else {
        return Ok(cpal::default_host());
    };
    let id = cpal::available_hosts()
        .into_iter()
        .find(|id| id.name().eq_ignore_ascii_case(name))
        .ok_or_else(|| {
            format!(
                "unknown audio host {name:?}: this system has {}",
                host_names().join(", ")
            )
        })?;
    cpal::host_from_id(id).map_err(|e| e.to_string())
}

pub fn device_name(device: &cpal::Device) -> String {
    device
        .description()
        .map(|d| d.name().to_string())
        .unwrap_or_else(|_| device.to_string())
}

fn device_id(device: &cpal::Device) -> String {
    device.id().map(|id| id.to_string()).unwrap_or_default()
}

fn find_device(host: &cpal::Host, name: Option<&str>, input: bool) -> Result<cpal::Device, String> {
    let which = if input { "input" } else { "output" };
    match name {
        None | Some("default") => {
            let device = if input {
                host.default_input_device()
            } else {
                host.default_output_device()
            };
            device.ok_or_else(|| format!("this system has no default audio {which} device"))
        }
        Some(name) => {
            let devices = host.devices().map_err(|e| e.to_string())?;
            let mut matches = devices.filter(|d| {
                (if input {
                    d.supports_input()
                } else {
                    d.supports_output()
                }) && (device_name(d) == name || device_id(d) == name)
            });
            matches
                .next()
                .ok_or_else(|| format!("no audio {which} device named {name:?}"))
        }
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

pub fn devices(host: Option<&str>) -> Result<Vec<DeviceInfo>, String> {
    let host = host_by_name(host)?;
    let host_name = host.id().name().to_string();
    let default_in = host.default_input_device().map(|d| device_id(&d));
    let default_out = host.default_output_device().map(|d| device_id(&d));
    let mut list = Vec::new();
    for device in host.devices().map_err(|e| e.to_string())? {
        let out = device.default_output_config().ok();
        let inp = device.default_input_config().ok();
        let range = |c: &cpal::SupportedStreamConfig| match c.buffer_size() {
            SupportedBufferSize::Range { min, max } => Some((*min, *max)),
            SupportedBufferSize::Unknown => None,
        };
        let id = device_id(&device);
        list.push(DeviceInfo {
            name: device_name(&device),
            host: host_name.clone(),
            inputs: inp.as_ref().map_or(0, |c| c.channels()),
            outputs: out.as_ref().map_or(0, |c| c.channels()),
            sample_rate: out.as_ref().or(inp.as_ref()).map(|c| c.sample_rate()),
            buffer_range: out.as_ref().or(inp.as_ref()).and_then(range),
            default_input: default_in.as_deref() == Some(id.as_str()),
            default_output: default_out.as_deref() == Some(id.as_str()),
            id,
        });
    }
    Ok(list)
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

/// Opens the device on a thread of its own, which keeps the streams (some systems tie them to
/// the thread that made them) until `Live::stop`.
pub fn open_device(
    graph: Arc<Mutex<Graph>>,
    request: Request,
    meters: Arc<Meters>,
) -> Result<(Live, Opened), String> {
    let (stop, stopped) = mpsc::channel::<()>();
    let (ready, opened) = mpsc::sync_channel::<Result<Opened, String>>(1);
    let handle = std::thread::Builder::new()
        .name("pyzed-audio-device".into())
        .spawn(move || {
            let streams = match build_streams(&graph, &request, &meters) {
                Ok((streams, opened)) => {
                    let _ = ready.send(Ok(opened));
                    streams
                }
                Err(error) => {
                    let _ = ready.send(Err(error));
                    return;
                }
            };
            let _ = stopped.recv();
            drop(streams);
        })
        .map_err(|e| e.to_string())?;
    match opened.recv() {
        Ok(Ok(opened)) => Ok((
            Live {
                stop,
                handle: Some(handle),
            },
            opened,
        )),
        Ok(Err(error)) => {
            let _ = handle.join();
            Err(error)
        }
        Err(_) => Err("the audio device thread stopped".into()),
    }
}

fn build_streams(
    graph: &Arc<Mutex<Graph>>,
    request: &Request,
    meters: &Arc<Meters>,
) -> Result<(Vec<cpal::Stream>, Opened), String> {
    let host = host_by_name(request.host.as_deref())?;
    let host_name = host.id().name().to_string();
    let device = find_device(&host, request.device.as_deref(), false)?;
    let default = device
        .default_output_config()
        .map_err(|e| format!("{}: {e}", device_name(&device)))?;
    let format = default.sample_format();
    let sr = request.sample_rate.unwrap_or(default.sample_rate());
    if request.sample_rate.is_some() {
        let supported = device
            .supported_output_configs()
            .map_err(|e| e.to_string())?
            .any(|c| {
                c.sample_format() == format
                    && c.min_sample_rate() <= sr
                    && sr <= c.max_sample_rate()
            });
        if !supported {
            return Err(format!("{} does not play at {sr} Hz", device_name(&device)));
        }
    }
    let wanted = request.buffer_size.or(recommended_buffer(&host_name));
    let buffer = match (wanted, default.buffer_size()) {
        (Some(n), SupportedBufferSize::Range { min, max }) => Some(n.clamp(*min, *max)),
        (n, _) => n,
    };
    let channels = default.channels();
    // The graph runs at the device's rate: resize delay lines and the like before it plays.
    {
        let mut g = graph.lock().map_err(|_| "the audio graph is broken")?;
        if g.sr != sr as f32 {
            g.reset(sr as f32);
        }
        g.input = None;
    }
    let mut config = StreamConfig {
        channels,
        sample_rate: sr,
        buffer_size: buffer.map_or(BufferSize::Default, BufferSize::Fixed),
    };
    let output = match output_stream(&device, config, format, graph, meters) {
        Ok(stream) => stream,
        // Not every system takes a fixed buffer (WASAPI in shared mode picks its own).
        Err(_) if buffer.is_some() => {
            config.buffer_size = BufferSize::Default;
            output_stream(&device, config, format, graph, meters)?
        }
        Err(error) => return Err(error),
    };
    let mut streams = vec![output];
    let mut input_name = None;
    if request.input || request.input_device.is_some() {
        let input = find_device(&host, request.input_device.as_deref(), true)?;
        input_name = Some(device_name(&input));
        streams.push(input_stream(&input, sr, config.buffer_size, graph, meters)?);
    }
    for stream in &streams {
        stream.play().map_err(|e| e.to_string())?;
    }
    let opened = Opened {
        backend: "device",
        host: host_name,
        device: device_name(&device),
        input_device: input_name,
        sample_rate: sr,
        buffer_size: match config.buffer_size {
            BufferSize::Fixed(n) => Some(n),
            BufferSize::Default => None,
        },
        channels,
        sample_format: format.to_string(),
    };
    Ok((streams, opened))
}

fn output_stream(
    device: &cpal::Device,
    config: StreamConfig,
    format: SampleFormat,
    graph: &Arc<Mutex<Graph>>,
    meters: &Arc<Meters>,
) -> Result<cpal::Stream, String> {
    macro_rules! build {
        ($($variant:ident => $t:ty),*) => {
            match format {
                $(SampleFormat::$variant => typed_output::<$t>(device, config, graph, meters),)*
                other => Err(format!("unsupported sample format {other}")),
            }
        };
    }
    build!(F32 => f32, F64 => f64, I16 => i16, I32 => i32, U16 => u16, U8 => u8, I8 => i8)
}

fn typed_output<T>(
    device: &cpal::Device,
    config: StreamConfig,
    graph: &Arc<Mutex<Graph>>,
    meters: &Arc<Meters>,
) -> Result<cpal::Stream, String>
where
    T: SizedSample + FromSample<f32>,
{
    let graph = graph.clone();
    let meters_cb = meters.clone();
    let meters_err = meters.clone();
    let channels = config.channels as usize;
    let sr = config.sample_rate as f32;
    let mut scratch: Vec<f32> = vec![0.0; 8192 * channels.max(2)];
    let mut flushed = false;
    device
        .build_output_stream(
            config,
            move |data: &mut [T], info: &cpal::OutputCallbackInfo| {
                if !flushed {
                    flush_denormals();
                    flushed = true;
                }
                let started = Instant::now();
                if scratch.len() < data.len() {
                    // Only when the system asks for more than ever before.
                    scratch.resize(data.len(), 0.0);
                }
                let buf = &mut scratch[..data.len()];
                match graph.try_lock() {
                    Ok(mut g) => g.render(buf, channels),
                    Err(_) => {
                        buf.fill(0.0);
                        meters_cb.underruns.fetch_add(1, Ordering::Relaxed);
                    }
                }
                for (out, &x) in data.iter_mut().zip(buf.iter()) {
                    *out = T::from_sample(x.clamp(-1.0, 1.0));
                }
                let frames = (data.len() / channels.max(1)) as f32;
                let load = started.elapsed().as_secs_f32() / (frames / sr);
                meters_cb.load.store(load.to_bits(), Ordering::Relaxed);
                let ts = info.timestamp();
                let latency = ts.playback.duration_since(ts.callback);
                meters_cb
                    .latency_us
                    .store(latency.as_micros() as u64, Ordering::Relaxed);
            },
            move |error| {
                if let Ok(mut slot) = meters_err.error.lock() {
                    *slot = Some(error.to_string());
                }
            },
            None,
        )
        .map_err(|e| e.to_string())
}

fn input_stream(
    device: &cpal::Device,
    sr: u32,
    buffer: BufferSize,
    graph: &Arc<Mutex<Graph>>,
    meters: &Arc<Meters>,
) -> Result<cpal::Stream, String> {
    let default = device.default_input_config().map_err(|e| e.to_string())?;
    let config = StreamConfig {
        channels: default.channels(),
        sample_rate: sr,
        buffer_size: buffer,
    };
    // Half a second of stereo frames between the input and the output callbacks.
    let (producer, consumer) = RingBuffer::<f32>::new(sr as usize);
    graph.lock().map_err(|_| "the audio graph is broken")?.input = Some(consumer);
    macro_rules! build {
        ($($variant:ident => $t:ty),*) => {
            match default.sample_format() {
                $(SampleFormat::$variant => typed_input::<$t>(device, config, producer, meters),)*
                other => Err(format!("unsupported sample format {other}")),
            }
        };
    }
    let built =
        build!(F32 => f32, F64 => f64, I16 => i16, I32 => i32, U16 => u16, U8 => u8, I8 => i8);
    built.map_err(|_| {
        format!(
            "{} does not record at {sr} Hz with this buffer",
            device_name(device)
        )
    })
}

fn typed_input<T>(
    device: &cpal::Device,
    config: StreamConfig,
    mut producer: rtrb::Producer<f32>,
    meters: &Arc<Meters>,
) -> Result<cpal::Stream, String>
where
    T: SizedSample,
    f32: FromSample<T>,
{
    let channels = config.channels as usize;
    let meters_err = meters.clone();
    device
        .build_input_stream(
            config,
            move |data: &[T], _: &cpal::InputCallbackInfo| {
                for frame in data.chunks(channels.max(1)) {
                    // Whole frames only, so left and right never swap.
                    if producer.slots() < 2 {
                        break;
                    }
                    let l: f32 = frame[0].to_sample();
                    let r: f32 = frame.get(1).map_or(l, |s| s.to_sample());
                    let _ = producer.push(l);
                    let _ = producer.push(r);
                }
            },
            move |error| {
                if let Ok(mut slot) = meters_err.error.lock() {
                    *slot = Some(error.to_string());
                }
            },
            None,
        )
        .map_err(|e| e.to_string())
}
