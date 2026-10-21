//! Audio devices through the system's own API (WASAPI or ASIO on Windows, CoreAudio on macOS,
//! PulseAudio/PipeWire or ALSA on Linux). On Linux this needs ALSA's development files, so a build
//! from source without them leaves it out (see `no_device.rs`).

use std::sync::atomic::Ordering;
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{BufferSize, FromSample, SampleFormat, SizedSample, StreamConfig, SupportedBufferSize};
use rtrb::RingBuffer;

use super::backend::{
    DeviceInfo, Live, Meters, Opened, Request, flush_denormals, recommended_buffer,
};
use super::graph::Graph;

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
