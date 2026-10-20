//! The audio engine behind `pyzed.audio`: a patch of modules (oscillators, filters, envelopes,
//! effects, sequencers...) connected by cables, computed in Rust on a real-time thread and
//! played on the system's audio device, or rendered offline without one.
//!
//! Python only ever talks to the control side ([`AudioEngine`]); every change reaches the audio
//! thread through a lock-free queue, so turning a knob never makes the sound wait.

mod backend;
mod catalog;
mod dsp;
mod graph;
mod midi;

use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::{Duration, Instant};

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use rtrb::{Consumer, Producer, PushError, RingBuffer};
use rustfft::FftPlanner;
use rustfft::num_complex::Complex;

use backend::{Live, Meters, Opened, Request};
use catalog::{ModuleSpec, Monitor};
use dsp::{BLOCK, Sample};
use graph::{Cmd, Graph, MAX_NODES, NodeRt, Schedule, Shared, Trash};

struct NodeCtl {
    spec: &'static ModuleSpec,
    params: Vec<f32>,
    shared: Arc<Shared>,
    /// Creation order: modules that do not depend on each other run in this order.
    seq: u64,
}

#[derive(Clone, Copy, PartialEq, Eq)]
struct Cable {
    src: usize,
    out: usize,
    dst: usize,
    inp: usize,
}

struct Inner {
    graph: Arc<Mutex<Graph>>,
    /// Shared with the graph, so reading them never locks it while it plays.
    master: Arc<Shared>,
    frames: Arc<AtomicU64>,
    commands: Producer<Cmd>,
    trash: Consumer<Trash>,
    nodes: Vec<Option<NodeCtl>>,
    cables: Vec<Cable>,
    seq: u64,
    sr: f32,
    live: Option<Live>,
    opened: Option<Opened>,
    meters: Arc<Meters>,
    started: Option<Instant>,
    planner: FftPlanner<f32>,
    midi_events: Option<Consumer<[u8; 3]>>,
    midi_inputs: Vec<(String, midir::MidiInputConnection<()>)>,
    midi_output: Option<midi::Output>,
}

/// The native side of `pyzed.audio.Engine`. Modules are addressed by slot numbers here; the
/// Python class gives them names.
#[pyclass(module = "pyzed._core", frozen)]
pub struct AudioEngine {
    inner: Mutex<Inner>,
    midi_hw: Arc<Mutex<Producer<[u8; 3]>>>,
}

fn err(message: impl Into<String>) -> PyErr {
    PyValueError::new_err(message.into())
}

impl Inner {
    fn node(&self, slot: usize) -> PyResult<&NodeCtl> {
        self.nodes
            .get(slot)
            .and_then(Option::as_ref)
            .ok_or_else(|| err(format!("no module in slot {slot}")))
    }

    fn graph(&self) -> MutexGuard<'_, Graph> {
        self.graph.lock().unwrap_or_else(|p| p.into_inner())
    }

    /// Sends a command to the audio thread. While nothing plays, the graph is applied right away
    /// (nobody else is reading the queue).
    fn send(&mut self, mut cmd: Cmd) -> PyResult<()> {
        let deadline = Instant::now() + Duration::from_secs(2);
        loop {
            match self.commands.push(cmd) {
                Ok(()) => break,
                Err(PushError::Full(back)) => {
                    cmd = back;
                    if self.live.is_none() {
                        self.graph().apply();
                    } else if Instant::now() > deadline {
                        return Err(PyRuntimeError::new_err(
                            "the audio thread stopped answering (was the device unplugged?); \
                             call engine.stop() and engine.start() again",
                        ));
                    } else {
                        std::thread::sleep(Duration::from_millis(1));
                    }
                }
            }
        }
        if self.live.is_none() {
            self.graph().apply();
        }
        self.empty_trash();
        Ok(())
    }

    fn empty_trash(&mut self) {
        while self.trash.pop().is_ok() {}
    }

    /// Recomputes the running order and the routes of every input after the cables change.
    fn schedule(&self) -> Box<Schedule> {
        let len = self.nodes.len();
        let mut routes: Vec<Vec<Vec<(usize, usize)>>> = self
            .nodes
            .iter()
            .map(|n| {
                n.as_ref()
                    .map_or(Vec::new(), |n| vec![Vec::new(); n.spec.inputs.len()])
            })
            .collect();
        let mut linked = vec![0u64; len];
        let mut indegree = vec![0usize; len];
        let mut next: Vec<Vec<usize>> = vec![Vec::new(); len];
        for c in &self.cables {
            routes[c.dst][c.inp].push((c.src, c.out));
            linked[c.dst] |= 1 << c.inp;
            if c.src != c.dst && !next[c.src].contains(&c.dst) {
                next[c.src].push(c.dst);
                indegree[c.dst] += 1;
            }
        }
        // Kahn's sort, in creation order. A loop has no first module: the oldest one waiting
        // runs, reading the rest of the loop from the previous block.
        let seq = |slot: usize| self.nodes[slot].as_ref().map_or(0, |n| n.seq);
        let live: Vec<usize> = (0..len).filter(|&s| self.nodes[s].is_some()).collect();
        let mut ready: BinaryHeap<Reverse<(u64, usize)>> = live
            .iter()
            .filter(|&&s| indegree[s] == 0)
            .map(|&s| Reverse((seq(s), s)))
            .collect();
        let mut done = vec![false; len];
        let mut order = Vec::with_capacity(live.len());
        while order.len() < live.len() {
            let slot = match ready.pop() {
                Some(Reverse((_, slot))) => slot,
                None => *live
                    .iter()
                    .filter(|&&s| !done[s])
                    .min_by_key(|&&s| seq(s))
                    .expect("a module left"),
            };
            if done[slot] {
                continue;
            }
            done[slot] = true;
            order.push(slot);
            for &dst in &next[slot] {
                indegree[dst] = indegree[dst].saturating_sub(1);
                if indegree[dst] == 0 && !done[dst] {
                    ready.push(Reverse((seq(dst), dst)));
                }
            }
        }
        Box::new(Schedule {
            order,
            routes,
            linked,
        })
    }

    fn reschedule(&mut self) -> PyResult<()> {
        let schedule = self.schedule();
        self.send(Cmd::Schedule(schedule))
    }

    fn stop(&mut self) {
        if let Some(live) = self.live.take() {
            live.stop();
        }
        self.opened = None;
        self.started = None;
        self.graph().apply();
        self.empty_trash();
    }

    fn shared(&self, slot: Option<usize>) -> PyResult<Arc<Shared>> {
        match slot {
            Some(slot) => Ok(self.node(slot)?.shared.clone()),
            None => Ok(self.master.clone()),
        }
    }
}

fn spec(kind: &str) -> PyResult<&'static ModuleSpec> {
    catalog::find(kind).map(|(_, s)| s).ok_or_else(|| {
        let kinds: Vec<_> = catalog::specs().iter().map(|s| s.kind).collect();
        err(format!(
            "unknown module {kind:?}; the modules are {}",
            kinds.join(", ")
        ))
    })
}

fn clamp_param(spec: &ModuleSpec, index: usize, value: f64) -> PyResult<f32> {
    let p = &spec.params[index];
    if !value.is_finite() {
        return Err(err(format!("{} must be a number", p.name)));
    }
    let mut v = (value as f32).clamp(p.min, p.max);
    if p.steps.is_some() {
        v = v.round();
    }
    Ok(v)
}

/// A spectrum in decibels (-120..0), `bins` bands spread evenly over octaves from 20 Hz (or
/// evenly over hertz with `log=False`) to half the sample rate.
fn spectrum(
    planner: &mut FftPlanner<f32>,
    samples: &[f32],
    sr: f32,
    bins: usize,
    log: bool,
) -> Vec<f32> {
    let n = samples.len();
    let window: Vec<f32> = (0..n)
        .map(|i| 0.5 - 0.5 * (std::f32::consts::TAU * i as f32 / n as f32).cos())
        .collect();
    let gain: f32 = window.iter().sum::<f32>() / 2.0;
    let mut buf: Vec<Complex<f32>> = samples
        .iter()
        .zip(&window)
        .map(|(x, w)| Complex::new(x * w, 0.0))
        .collect();
    planner.plan_fft_forward(n).process(&mut buf);
    let half = n / 2;
    let mags: Vec<f32> = buf[..half].iter().map(|c| c.norm() / gain).collect();
    let hz_per_bin = sr / n as f32;
    let nyquist = sr / 2.0;
    let edge = |j: usize| {
        let t = j as f32 / bins as f32;
        if log {
            20.0 * (nyquist / 20.0).powf(t)
        } else {
            nyquist * t
        }
    };
    (0..bins)
        .map(|j| {
            let (lo, hi) = (edge(j) / hz_per_bin, edge(j + 1) / hz_per_bin);
            let (a, b) = (lo.floor() as usize, (hi.ceil() as usize).min(half));
            let peak = if b > a + 1 {
                mags[a.min(half - 1)..b].iter().copied().fold(0.0, f32::max)
            } else {
                // A band narrower than one FFT bin reads between the two nearest.
                let at = ((lo + hi) / 2.0).min((half - 2) as f32);
                let (i, frac) = (at as usize, at.fract());
                mags[i] + (mags[i + 1] - mags[i]) * frac
            };
            (20.0 * peak.max(1e-6).log10()).clamp(-120.0, 0.0)
        })
        .collect()
}

#[pymethods]
impl AudioEngine {
    #[new]
    #[pyo3(signature = (sample_rate=48000.0))]
    fn new(sample_rate: f32) -> PyResult<Self> {
        if !(8000.0..=384000.0).contains(&sample_rate) {
            return Err(err("sample_rate must be between 8000 and 384000"));
        }
        let (commands, commands_rx) = RingBuffer::new(4096);
        let (trash_tx, trash) = RingBuffer::new(4096);
        let (midi_tx, midi_rx) = RingBuffer::new(1024);
        let (midi_out_tx, midi_out_rx) = RingBuffer::new(1024);
        let mut graph = Graph::new(sample_rate, commands_rx, trash_tx, midi_rx);
        graph.midi_out = Some(midi_out_tx);
        let (master, frames) = (graph.master_shared.clone(), graph.frames.clone());
        Ok(AudioEngine {
            inner: Mutex::new(Inner {
                graph: Arc::new(Mutex::new(graph)),
                master,
                frames,
                commands,
                trash,
                nodes: Vec::new(),
                cables: Vec::new(),
                seq: 0,
                sr: sample_rate,
                live: None,
                opened: None,
                meters: Arc::new(Meters::default()),
                started: None,
                planner: FftPlanner::new(),
                midi_events: Some(midi_out_rx),
                midi_inputs: Vec::new(),
                midi_output: None,
            }),
            midi_hw: Arc::new(Mutex::new(midi_tx)),
        })
    }

    /// Adds a module and returns its slot.
    #[pyo3(signature = (kind, params=None))]
    fn add(&self, kind: &str, params: Option<&Bound<'_, PyDict>>) -> PyResult<usize> {
        let spec = spec(kind)?;
        let mut values: Vec<f32> = spec.params.iter().map(|p| p.default).collect();
        if let Some(params) = params {
            for (key, value) in params.iter() {
                let name: String = key.extract()?;
                let index = spec
                    .param(&name)
                    .ok_or_else(|| unknown_param(spec, &name))?;
                values[index] = clamp_param(spec, index, value.extract()?)?;
            }
        }
        let mut inner = self.lock();
        let slot = match inner.nodes.iter().position(Option::is_none) {
            Some(slot) => slot,
            None if inner.nodes.len() < MAX_NODES => {
                inner.nodes.push(None);
                inner.nodes.len() - 1
            }
            None => return Err(err(format!("a patch holds at most {MAX_NODES} modules"))),
        };
        let shared = Arc::new(Shared::new(spec.outputs.len(), spec.state.len()));
        let node = Box::new(NodeRt {
            dsp: dsp::create(spec.kind, inner.sr),
            params: values.clone(),
            ins: vec![[0.0; BLOCK]; spec.inputs.len()],
            outs: vec![[0.0; BLOCK]; spec.outputs.len()],
            shared: shared.clone(),
            monitor: match spec.monitor {
                Monitor::Output(i) => (true, i),
                Monitor::Input(i) => (false, i),
            },
        });
        inner.seq += 1;
        let seq = inner.seq;
        inner.nodes[slot] = Some(NodeCtl {
            spec,
            params: values,
            shared,
            seq,
        });
        inner.send(Cmd::Add(slot, node))?;
        inner.reschedule()?;
        Ok(slot)
    }

    fn remove(&self, slot: usize) -> PyResult<()> {
        let mut inner = self.lock();
        inner.node(slot)?;
        inner.cables.retain(|c| c.src != slot && c.dst != slot);
        inner.nodes[slot] = None;
        inner.reschedule()?;
        inner.send(Cmd::Remove(slot))
    }

    /// Plugs output `out` of `src` into input `inp` of `dst`. Returns False if that cable was
    /// already there.
    fn connect(&self, src: usize, out: &str, dst: usize, inp: &str) -> PyResult<bool> {
        let mut inner = self.lock();
        let cable = cable(&inner, src, out, dst, inp)?;
        if inner.cables.contains(&cable) {
            return Ok(false);
        }
        inner.cables.push(cable);
        inner.reschedule()?;
        Ok(true)
    }

    fn disconnect(&self, src: usize, out: &str, dst: usize, inp: &str) -> PyResult<bool> {
        let mut inner = self.lock();
        let cable = cable(&inner, src, out, dst, inp)?;
        let before = inner.cables.len();
        inner.cables.retain(|c| *c != cable);
        if inner.cables.len() == before {
            return Ok(false);
        }
        inner.reschedule()?;
        Ok(true)
    }

    /// Every cable as `(src, out, dst, inp)` with slots and port names.
    fn cables(&self) -> Vec<(usize, String, usize, String)> {
        let inner = self.lock();
        inner
            .cables
            .iter()
            .map(|c| {
                let (s, d) = (
                    inner.nodes[c.src].as_ref().unwrap(),
                    inner.nodes[c.dst].as_ref().unwrap(),
                );
                (
                    c.src,
                    s.spec.outputs[c.out].name.clone(),
                    c.dst,
                    d.spec.inputs[c.inp].name.clone(),
                )
            })
            .collect()
    }

    fn slots(&self) -> Vec<usize> {
        let inner = self.lock();
        let mut slots: Vec<_> = inner
            .nodes
            .iter()
            .enumerate()
            .filter_map(|(i, n)| n.as_ref().map(|n| (n.seq, i)))
            .collect();
        slots.sort();
        slots.into_iter().map(|(_, i)| i).collect()
    }

    fn kind(&self, slot: usize) -> PyResult<&'static str> {
        Ok(self.lock().node(slot)?.spec.kind)
    }

    /// Sets a parameter (clamped to its range) and returns the value it took.
    fn set(&self, slot: usize, param: &str, value: f64) -> PyResult<f32> {
        let mut inner = self.lock();
        let spec = inner.node(slot)?.spec;
        let index = spec
            .param(param)
            .ok_or_else(|| unknown_param(spec, param))?;
        let value = clamp_param(spec, index, value)?;
        inner.nodes[slot].as_mut().unwrap().params[index] = value;
        inner.send(Cmd::Param(slot, index, value))?;
        Ok(value)
    }

    fn get(&self, slot: usize, param: &str) -> PyResult<f32> {
        let inner = self.lock();
        let node = inner.node(slot)?;
        let index = node
            .spec
            .param(param)
            .ok_or_else(|| unknown_param(node.spec, param))?;
        Ok(node.params[index])
    }

    fn params<'py>(&self, py: Python<'py>, slot: usize) -> PyResult<Bound<'py, PyDict>> {
        let inner = self.lock();
        let node = inner.node(slot)?;
        let dict = PyDict::new(py);
        for (p, v) in node.spec.params.iter().zip(&node.params) {
            dict.set_item(&p.name, *v)?;
        }
        Ok(dict)
    }

    fn trigger(&self, slot: usize) -> PyResult<()> {
        let mut inner = self.lock();
        inner.node(slot)?;
        inner.send(Cmd::Trigger(slot))
    }

    /// Gives a sampler its sound: one list of samples per channel (one or two).
    fn load_sample(
        &self,
        py: Python<'_>,
        slot: usize,
        channels: Vec<Vec<f32>>,
        sample_rate: f32,
    ) -> PyResult<()> {
        if channels.is_empty() || channels.iter().any(|c| c.len() != channels[0].len()) {
            return Err(err("the channels of a sample must have the same length"));
        }
        if sample_rate <= 0.0 {
            return Err(err("sample_rate must be positive"));
        }
        let sample = Arc::new(Sample {
            channels: channels.into_iter().take(2).collect(),
            sample_rate,
        });
        py.detach(|| {
            let mut inner = self.lock();
            inner.node(slot)?;
            inner.send(Cmd::Sample(slot, Some(sample)))
        })
    }

    /// Reads a WAV file into a sampler. Returns `(frames, sample_rate, channels)`.
    fn load_wav(
        &self,
        py: Python<'_>,
        slot: usize,
        path: std::path::PathBuf,
    ) -> PyResult<(usize, u32, u16)> {
        let sample = py
            .detach(|| read_wav(&path))
            .map_err(|e| err(format!("{}: {e}", path.display())))?;
        let (frames, sr, channels) = (
            sample.len(),
            sample.sample_rate as u32,
            sample.channels.len() as u16,
        );
        let mut inner = self.lock();
        inner.node(slot)?;
        inner.send(Cmd::Sample(slot, Some(Arc::new(sample))))?;
        Ok((frames, sr, channels))
    }

    /// Sends a MIDI message to the patch, as if it came from a keyboard.
    fn midi(&self, status: u8, data1: u8, data2: u8) -> PyResult<()> {
        self.lock()
            .send(Cmd::Midi([status, data1 & 0x7f, data2 & 0x7f]))
    }

    /// The last `n` samples a module (or the whole output, with `None`) played.
    #[pyo3(signature = (slot, n=1024))]
    fn scope(&self, slot: Option<usize>, n: usize) -> PyResult<Vec<f32>> {
        Ok(self.lock().shared(slot)?.recent(n))
    }

    /// The spectrum of a module (or the whole output) in decibels.
    #[pyo3(signature = (slot, bins=256, size=2048, log=true))]
    fn spectrum(
        &self,
        slot: Option<usize>,
        bins: usize,
        size: usize,
        log: bool,
    ) -> PyResult<Vec<f32>> {
        if !size.is_power_of_two() || !(64..=graph::RING).contains(&size) {
            return Err(err(format!(
                "size must be a power of two from 64 to {}",
                graph::RING
            )));
        }
        if bins == 0 || bins > size / 2 {
            return Err(err("bins must be between 1 and size / 2"));
        }
        let mut inner = self.lock();
        let samples = inner.shared(slot)?.recent(size);
        let sr = inner.sr;
        Ok(spectrum(&mut inner.planner, &samples, sr, bins, log))
    }

    /// `(rms, peak)` of a module's signal (or the whole output).
    fn level(&self, slot: Option<usize>) -> PyResult<(f32, f32)> {
        let shared = self.lock().shared(slot)?;
        Ok((Shared::load(&shared.rms), Shared::load(&shared.peak)))
    }

    /// The latest value of an output (`None` = the left and right of the whole output).
    fn probe(&self, slot: Option<usize>, port: &str) -> PyResult<f32> {
        let inner = self.lock();
        let (shared, index) = match slot {
            Some(slot) => {
                let node = inner.node(slot)?;
                let index = node
                    .spec
                    .output(port)
                    .ok_or_else(|| err(format!("{} has no output {port:?}", node.spec.kind)))?;
                (node.shared.clone(), index)
            }
            None => (inner.shared(None)?, (port == "right") as usize),
        };
        Ok(Shared::load(&shared.probes[index]))
    }

    fn state<'py>(&self, py: Python<'py>, slot: usize) -> PyResult<Bound<'py, PyDict>> {
        let inner = self.lock();
        let node = inner.node(slot)?;
        let dict = PyDict::new(py);
        for (name, cell) in node.spec.state.iter().zip(node.shared.state.iter()) {
            dict.set_item(*name, Shared::load(cell))?;
        }
        Ok(dict)
    }

    /// Starts playing. `backend` is "device" (the sound card), "null" (a clock with no sound)
    /// or "auto" (the device, else the null clock). Returns what opened.
    #[pyo3(signature = (backend="auto", host=None, device=None, input=false, input_device=None, sample_rate=None, buffer_size=None))]
    #[allow(clippy::too_many_arguments)]
    fn start<'py>(
        &self,
        py: Python<'py>,
        backend: &str,
        host: Option<String>,
        device: Option<String>,
        input: bool,
        input_device: Option<String>,
        sample_rate: Option<u32>,
        buffer_size: Option<u32>,
    ) -> PyResult<Bound<'py, PyDict>> {
        if let Some(n) = buffer_size
            && !(16..=8192).contains(&n)
        {
            return Err(err("buffer_size must be between 16 and 8192 frames"));
        }
        let request = Request {
            host,
            device,
            input,
            input_device,
            sample_rate,
            buffer_size,
        };
        py.detach(|| {
            let mut inner = self.lock();
            inner.stop();
            inner.meters = Arc::new(Meters::default());
            let graph = inner.graph.clone();
            let meters = inner.meters.clone();
            let opened = match backend {
                "device" | "auto" => {
                    match backend::open_device(graph.clone(), request.clone(), meters.clone()) {
                        Ok(opened) => Ok(opened),
                        Err(error) if backend == "auto" => {
                            let sr = request.sample_rate.unwrap_or(inner.sr as u32);
                            reset_rate(&graph, sr);
                            let (live, mut opened) = backend::open_null(
                                graph,
                                sr,
                                request.buffer_size.unwrap_or(256),
                                meters.clone(),
                            );
                            opened.backend = "null";
                            *meters.error.lock().unwrap() =
                                Some(format!("no audio device ({error}); playing silently"));
                            Ok((live, opened))
                        }
                        Err(error) => Err(PyRuntimeError::new_err(error)),
                    }
                }
                "null" => {
                    let sr = request.sample_rate.unwrap_or(inner.sr as u32);
                    reset_rate(&graph, sr);
                    Ok(backend::open_null(
                        graph,
                        sr,
                        request.buffer_size.unwrap_or(256),
                        meters,
                    ))
                }
                other => Err(err(format!(
                    "unknown backend {other:?}: use \"auto\", \"device\" or \"null\""
                ))),
            }?;
            let (live, opened) = opened;
            inner.sr = opened.sample_rate as f32;
            inner.live = Some(live);
            inner.opened = Some(opened);
            inner.started = Some(Instant::now());
            Ok::<_, PyErr>(())
        })?;
        self.info(py)
    }

    fn stop(&self, py: Python<'_>) {
        py.detach(|| self.lock().stop());
    }

    fn info<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let inner = self.lock();
        let dict = PyDict::new(py);
        dict.set_item("running", inner.live.is_some())?;
        dict.set_item("sample_rate", inner.sr as u32)?;
        if let Some(o) = &inner.opened {
            dict.set_item("backend", o.backend)?;
            dict.set_item("host", &o.host)?;
            dict.set_item("device", &o.device)?;
            dict.set_item("input_device", &o.input_device)?;
            dict.set_item("buffer_size", o.buffer_size)?;
            dict.set_item("channels", o.channels)?;
            dict.set_item("sample_format", &o.sample_format)?;
        } else {
            dict.set_item("backend", "offline")?;
        }
        let m = &inner.meters;
        let latency = m.latency_us.load(Ordering::Relaxed) as f64 / 1000.0;
        let buffer_ms = inner
            .opened
            .as_ref()
            .and_then(|o| o.buffer_size)
            .map(|n| n as f64 / inner.sr as f64 * 1000.0);
        dict.set_item(
            "latency_ms",
            if latency > 0.0 {
                Some(latency)
            } else {
                buffer_ms
            },
        )?;
        dict.set_item("load", f32::from_bits(m.load.load(Ordering::Relaxed)))?;
        dict.set_item("underruns", m.underruns.load(Ordering::Relaxed))?;
        dict.set_item("error", m.error.lock().ok().and_then(|e| e.clone()))?;
        dict.set_item(
            "time",
            inner.frames.load(Ordering::Relaxed) as f64 / inner.sr as f64,
        )?;
        dict.set_item("modules", inner.nodes.iter().flatten().count())?;
        dict.set_item(
            "midi_inputs",
            inner
                .midi_inputs
                .iter()
                .map(|(n, _)| n.clone())
                .collect::<Vec<_>>(),
        )?;
        dict.set_item(
            "midi_output",
            inner.midi_output.as_ref().map(|o| o.name.clone()),
        )?;
        Ok(dict)
    }

    /// Renders `frames` without a device, as fast as the processor allows. Returns `(left, right)`.
    fn render(&self, py: Python<'_>, frames: usize) -> PyResult<(Vec<f32>, Vec<f32>)> {
        py.detach(|| {
            let inner = self.lock();
            if inner.live.is_some() {
                return Err(PyRuntimeError::new_err(
                    "the engine is playing: call engine.stop() before rendering offline",
                ));
            }
            let mut buf = vec![0.0f32; frames * 2];
            inner.graph().render(&mut buf, 2);
            let left = buf.iter().step_by(2).copied().collect();
            let right = buf.iter().skip(1).step_by(2).copied().collect();
            Ok((left, right))
        })
    }

    /// Opens a MIDI input (the first whose name contains `name`, or the first of all), or a
    /// virtual port other programs can play into. Returns the port's name.
    #[pyo3(signature = (name=None, virtual_name=None))]
    fn open_midi_input(&self, name: Option<&str>, virtual_name: Option<&str>) -> PyResult<String> {
        let (conn, port) = midi::open_input(name, virtual_name, self.midi_hw.clone())
            .map_err(PyRuntimeError::new_err)?;
        self.lock().midi_inputs.push((port.clone(), conn));
        Ok(port)
    }

    fn close_midi_inputs(&self) {
        for (_, conn) in self.lock().midi_inputs.drain(..) {
            conn.close();
        }
    }

    /// Opens the MIDI output the `midi_out` modules play on. Returns the port's name.
    #[pyo3(signature = (name=None, virtual_name=None))]
    fn open_midi_output(&self, name: Option<&str>, virtual_name: Option<&str>) -> PyResult<String> {
        let mut inner = self.lock();
        let events = match inner.midi_output.take() {
            Some(old) => old.close(),
            None => inner.midi_events.take(),
        };
        let Some(events) = events else {
            return Err(PyRuntimeError::new_err("the MIDI output queue was lost"));
        };
        match midi::Output::open(name, virtual_name, events) {
            Ok(output) => {
                let name = output.name.clone();
                inner.midi_output = Some(output);
                Ok(name)
            }
            Err((error, events)) => {
                inner.midi_events = Some(events);
                Err(PyRuntimeError::new_err(error))
            }
        }
    }

    fn close_midi_output(&self) {
        let mut inner = self.lock();
        if let Some(output) = inner.midi_output.take() {
            inner.midi_events = output.close();
        }
    }

    /// Sends raw bytes to the MIDI output.
    fn send_midi(&self, message: Vec<u8>) -> PyResult<()> {
        let inner = self.lock();
        let output = inner.midi_output.as_ref().ok_or_else(|| {
            PyRuntimeError::new_err("no MIDI output is open (engine.open_midi_output)")
        })?;
        output.send(&message).map_err(PyRuntimeError::new_err)
    }
}

impl AudioEngine {
    fn lock(&self) -> MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(|p| p.into_inner())
    }
}

impl Drop for AudioEngine {
    fn drop(&mut self) {
        let inner = self.inner.get_mut().unwrap_or_else(|p| p.into_inner());
        inner.stop();
        if let Some(output) = inner.midi_output.take() {
            output.close();
        }
    }
}

fn reset_rate(graph: &Arc<Mutex<Graph>>, sr: u32) {
    let mut g = graph.lock().unwrap_or_else(|p| p.into_inner());
    if g.sr != sr as f32 {
        g.reset(sr as f32);
    }
    g.input = None;
}

fn unknown_param(spec: &ModuleSpec, name: &str) -> PyErr {
    let names: Vec<_> = spec.params.iter().map(|p| p.name.as_str()).collect();
    err(format!(
        "{} has no parameter {name:?}; its parameters are {}",
        spec.kind,
        names.join(", ")
    ))
}

fn cable(inner: &Inner, src: usize, out: &str, dst: usize, inp: &str) -> PyResult<Cable> {
    let (s, d) = (inner.node(src)?.spec, inner.node(dst)?.spec);
    let out_index = s.output(out).ok_or_else(|| {
        let names: Vec<_> = s.outputs.iter().map(|p| p.name.as_str()).collect();
        err(format!(
            "{} has no output {out:?}; its outputs are {}",
            s.kind,
            names.join(", ")
        ))
    })?;
    let in_index = d.input(inp).ok_or_else(|| {
        let names: Vec<_> = d.inputs.iter().map(|p| p.name.as_str()).collect();
        err(format!(
            "{} has no input {inp:?}; its inputs are {}",
            d.kind,
            names.join(", ")
        ))
    })?;
    Ok(Cable {
        src,
        out: out_index,
        dst,
        inp: in_index,
    })
}

fn read_wav(path: &std::path::Path) -> Result<Sample, String> {
    let mut reader = hound::WavReader::open(path).map_err(|e| e.to_string())?;
    let spec = reader.spec();
    let channels = spec.channels.max(1) as usize;
    let samples: Vec<f32> = match spec.sample_format {
        hound::SampleFormat::Float => reader.samples::<f32>().collect::<Result<_, _>>(),
        hound::SampleFormat::Int => {
            let scale = 1.0 / (1i64 << (spec.bits_per_sample - 1)) as f32;
            reader
                .samples::<i32>()
                .map(|s| s.map(|s| s as f32 * scale))
                .collect::<Result<_, _>>()
        }
    }
    .map_err(|e| e.to_string())?;
    let used = channels.min(2);
    let mut out = vec![Vec::with_capacity(samples.len() / channels); used];
    for frame in samples.chunks(channels) {
        for (ch, buf) in out.iter_mut().enumerate() {
            buf.push(frame[ch.min(frame.len() - 1)]);
        }
    }
    Ok(Sample {
        channels: out,
        sample_rate: spec.sample_rate as f32,
    })
}

/// The catalog as Python dictionaries (wrapped in dataclasses by `pyzed.audio`).
#[pyfunction]
fn audio_modules(py: Python<'_>) -> PyResult<Vec<Bound<'_, PyDict>>> {
    catalog::specs()
        .iter()
        .map(|s| {
            let d = PyDict::new(py);
            d.set_item("kind", s.kind)?;
            d.set_item("label", s.label)?;
            d.set_item("category", s.category)?;
            d.set_item("description", s.description)?;
            let ports = |ports: &[catalog::PortSpec]| -> PyResult<Vec<Bound<'_, PyDict>>> {
                ports
                    .iter()
                    .map(|p| {
                        let d = PyDict::new(py);
                        d.set_item("name", &p.name)?;
                        d.set_item("label", &p.label)?;
                        d.set_item("type", p.kind.name())?;
                        Ok(d)
                    })
                    .collect()
            };
            d.set_item("inputs", ports(&s.inputs)?)?;
            d.set_item("outputs", ports(&s.outputs)?)?;
            let params: PyResult<Vec<_>> = s
                .params
                .iter()
                .map(|p| {
                    let d = PyDict::new(py);
                    d.set_item("name", &p.name)?;
                    d.set_item("label", &p.label)?;
                    d.set_item("min", p.min)?;
                    d.set_item("max", p.max)?;
                    d.set_item("default", p.default)?;
                    d.set_item("unit", p.unit)?;
                    d.set_item("curve", if p.log { "log" } else { "lin" })?;
                    d.set_item("steps", p.steps)?;
                    d.set_item(
                        "options",
                        if p.options.is_empty() {
                            None
                        } else {
                            Some(p.options.clone())
                        },
                    )?;
                    Ok(d)
                })
                .collect();
            d.set_item("params", params?)?;
            d.set_item("state", s.state.clone())?;
            Ok(d)
        })
        .collect()
}

#[pyfunction]
fn audio_hosts() -> (Vec<String>, String) {
    (backend::host_names(), backend::default_host_name())
}

#[pyfunction]
#[pyo3(signature = (host=None))]
fn audio_devices<'py>(py: Python<'py>, host: Option<&str>) -> PyResult<Vec<Bound<'py, PyDict>>> {
    let list = py
        .detach(|| backend::devices(host))
        .map_err(PyRuntimeError::new_err)?;
    list.into_iter()
        .map(|d| {
            let dict = PyDict::new(py);
            dict.set_item("name", d.name)?;
            dict.set_item("id", d.id)?;
            dict.set_item("host", d.host)?;
            dict.set_item("inputs", d.inputs)?;
            dict.set_item("outputs", d.outputs)?;
            dict.set_item("sample_rate", d.sample_rate)?;
            dict.set_item("buffer_range", d.buffer_range)?;
            dict.set_item("default_input", d.default_input)?;
            dict.set_item("default_output", d.default_output)?;
            Ok(dict)
        })
        .collect()
}

#[pyfunction]
fn audio_recommended_buffer(host: &str) -> Option<u32> {
    backend::recommended_buffer(host)
}

#[pyfunction]
fn midi_ports() -> (Vec<String>, Vec<String>) {
    (
        midi::inputs().unwrap_or_default(),
        midi::outputs().unwrap_or_default(),
    )
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AudioEngine>()?;
    m.add_function(wrap_pyfunction!(audio_modules, m)?)?;
    m.add_function(wrap_pyfunction!(audio_hosts, m)?)?;
    m.add_function(wrap_pyfunction!(audio_devices, m)?)?;
    m.add_function(wrap_pyfunction!(audio_recommended_buffer, m)?)?;
    m.add_function(wrap_pyfunction!(midi_ports, m)?)?;
    m.add("AUDIO_BLOCK", BLOCK)?;
    Ok(())
}
