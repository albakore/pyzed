//! The patch as the audio thread runs it. The control side (Python) never touches it while it
//! plays: it sends commands through a lock-free queue, and whatever the audio thread lets go of
//! (a removed module, an old schedule, a replaced sample) travels back to be freed there.

use std::sync::Arc;
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};

use rtrb::{Consumer, Producer};

use super::dsp::{BLOCK, Block, Ctx, Dsp, Io, Sample};

/// The most modules a patch holds.
pub const MAX_NODES: usize = 1024;
/// The recent signal of each module kept for scopes and spectra (a power of two).
pub const RING: usize = 8192;

/// What the audio thread publishes about a module for the interface to draw: its recent signal,
/// its level, the last value of each output and the values of its `state`. Plain atomics, so
/// reading never makes the audio wait.
pub struct Shared {
    pub ring: Box<[AtomicU32]>,
    /// Samples written to `ring` so far.
    pub head: AtomicU64,
    pub rms: AtomicU32,
    pub peak: AtomicU32,
    pub probes: Box<[AtomicU32]>,
    pub state: Box<[AtomicU32]>,
}

fn atomics(n: usize) -> Box<[AtomicU32]> {
    (0..n).map(|_| AtomicU32::new(0)).collect()
}

impl Shared {
    pub fn new(outputs: usize, state: usize) -> Self {
        Shared {
            ring: atomics(RING),
            head: AtomicU64::new(0),
            rms: AtomicU32::new(0),
            peak: AtomicU32::new(0),
            probes: atomics(outputs),
            state: atomics(state),
        }
    }

    pub fn load(cell: &AtomicU32) -> f32 {
        f32::from_bits(cell.load(Ordering::Relaxed))
    }

    /// Records a block of the monitored signal and updates the meters: the peak falls back about
    /// 20 dB a second and the RMS averages over about 300 ms.
    fn record(&self, block: &Block, sr: f32) {
        let head = self.head.load(Ordering::Relaxed);
        let mut peak: f32 = 0.0;
        let mut sum = 0.0;
        for (i, &x) in block.iter().enumerate() {
            let x = if x.is_finite() { x } else { 0.0 };
            self.ring[(head as usize + i) & (RING - 1)].store(x.to_bits(), Ordering::Relaxed);
            peak = peak.max(x.abs());
            sum += x * x;
        }
        self.head.store(head + BLOCK as u64, Ordering::Release);
        let seconds = BLOCK as f32 / sr;
        let fall = 10f32.powf(-20.0 * seconds / 20.0);
        let held = Self::load(&self.peak) * fall;
        self.peak.store(peak.max(held).to_bits(), Ordering::Relaxed);
        let coef = 1.0 - (-seconds / 0.3).exp();
        let mean = Self::load(&self.rms).powi(2);
        let rms = (mean + (sum / BLOCK as f32 - mean) * coef).max(0.0).sqrt();
        self.rms.store(rms.to_bits(), Ordering::Relaxed);
    }

    /// The last `n` samples, oldest first.
    pub fn recent(&self, n: usize) -> Vec<f32> {
        let n = n.min(RING);
        let head = self.head.load(Ordering::Acquire) as usize;
        (0..n)
            .map(|i| {
                let at = (head + RING - n + i) & (RING - 1);
                if head + i < n {
                    0.0
                } else {
                    Self::load(&self.ring[at])
                }
            })
            .collect()
    }
}

/// A module on the audio thread.
pub struct NodeRt {
    pub dsp: Box<dyn Dsp>,
    pub params: Vec<f32>,
    pub ins: Vec<Block>,
    pub outs: Vec<Block>,
    pub shared: Arc<Shared>,
    /// Which signal feeds the scope: `(true, i)` for output `i`, `(false, i)` for input `i`.
    pub monitor: (bool, usize),
}

/// The order to run the modules in and where each input reads from, computed off the audio thread
/// whenever the cables change.
#[derive(Default)]
pub struct Schedule {
    pub order: Vec<usize>,
    /// For each slot and input, the `(slot, output)` pairs summed into it.
    pub routes: Vec<Vec<Vec<(usize, usize)>>>,
    /// For each slot, the bit mask of its inputs that have a cable.
    pub linked: Vec<u64>,
}

pub enum Cmd {
    Add(usize, Box<NodeRt>),
    Remove(usize),
    Schedule(Box<Schedule>),
    Param(usize, usize, f32),
    Trigger(usize),
    Sample(usize, Option<Arc<Sample>>),
    Midi([u8; 3]),
}

/// Things the audio thread lets go of, to be freed on the control side.
pub enum Trash {
    Node(#[allow(dead_code)] Box<NodeRt>),
    Schedule(#[allow(dead_code)] Box<Schedule>),
    Sample(#[allow(dead_code)] Arc<Sample>),
}

pub struct Graph {
    pub sr: f32,
    slots: Vec<Option<Box<NodeRt>>>,
    schedule: Box<Schedule>,
    commands: Consumer<Cmd>,
    trash: Producer<Trash>,
    midi_hw: Consumer<[u8; 3]>,
    midi: Vec<[u8; 3]>,
    pub midi_out: Option<Producer<[u8; 3]>>,
    midi_out_buf: Vec<[u8; 3]>,
    /// Interleaved stereo frames from the input device.
    pub input: Option<Consumer<f32>>,
    audio_in: [Block; 2],
    master: [Block; 2],
    pub master_shared: Arc<Shared>,
    /// What is left of the last block for the device's next callback.
    pending: [Block; 2],
    pending_at: usize,
    pub frames: u64,
}

impl Graph {
    pub fn new(
        sr: f32,
        commands: Consumer<Cmd>,
        trash: Producer<Trash>,
        midi_hw: Consumer<[u8; 3]>,
    ) -> Self {
        Graph {
            sr,
            slots: (0..MAX_NODES).map(|_| None).collect(),
            schedule: Box::default(),
            commands,
            trash,
            midi_hw,
            midi: Vec::with_capacity(512),
            midi_out: None,
            midi_out_buf: Vec::with_capacity(256),
            input: None,
            audio_in: [[0.0; BLOCK]; 2],
            master: [[0.0; BLOCK]; 2],
            master_shared: Arc::new(Shared::new(2, 0)),
            pending: [[0.0; BLOCK]; 2],
            pending_at: BLOCK,
            frames: 0,
        }
    }

    fn discard(&mut self, item: Trash) {
        // When the control side is behind, freeing here is better than leaking.
        let _ = self.trash.push(item);
    }

    /// Applies the queued commands; called at the start of every block.
    pub fn apply(&mut self) {
        while let Ok(cmd) = self.commands.pop() {
            match cmd {
                Cmd::Add(slot, node) => {
                    if let Some(old) = self.slots[slot].replace(node) {
                        self.discard(Trash::Node(old));
                    }
                }
                Cmd::Remove(slot) => {
                    if let Some(old) = self.slots[slot].take() {
                        self.discard(Trash::Node(old));
                    }
                }
                Cmd::Schedule(schedule) => {
                    let old = std::mem::replace(&mut self.schedule, schedule);
                    self.discard(Trash::Schedule(old));
                }
                Cmd::Param(slot, index, value) => {
                    if let Some(node) = self.slots[slot].as_mut()
                        && let Some(param) = node.params.get_mut(index)
                    {
                        *param = value;
                    }
                }
                Cmd::Trigger(slot) => {
                    if let Some(node) = self.slots[slot].as_mut() {
                        node.dsp.trigger();
                    }
                }
                Cmd::Sample(slot, sample) => {
                    let old = match self.slots[slot].as_mut() {
                        Some(node) => node.dsp.set_sample(sample),
                        None => sample,
                    };
                    if let Some(old) = old {
                        self.discard(Trash::Sample(old));
                    }
                }
                Cmd::Midi(msg) => {
                    if self.midi.len() < self.midi.capacity() {
                        self.midi.push(msg);
                    }
                }
            }
        }
    }

    /// Resizes every module's buffers for a new sample rate (only while stopped).
    pub fn reset(&mut self, sr: f32) {
        self.sr = sr;
        for node in self.slots.iter_mut().flatten() {
            node.dsp.reset(sr);
        }
    }

    /// Runs the whole patch for one block into `master`.
    fn block(&mut self) {
        self.apply();
        while self.midi.len() < self.midi.capacity()
            && let Ok(msg) = self.midi_hw.pop()
        {
            self.midi.push(msg);
        }
        self.read_input();
        for ch in &mut self.master {
            ch.fill(0.0);
        }
        let sr = self.sr;
        let schedule = &*self.schedule;
        for &slot in &schedule.order {
            let Some(mut node) = self.slots[slot].take() else {
                continue;
            };
            // Each input sums every cable plugged into it. A cable from a module that runs later
            // (a feedback loop) reads that module's previous block.
            for (input, sources) in node.ins.iter_mut().zip(&schedule.routes[slot]) {
                input.fill(0.0);
                for &(src, out) in sources {
                    let block = if src == slot {
                        node.outs.get(out)
                    } else {
                        self.slots[src].as_ref().and_then(|n| n.outs.get(out))
                    };
                    if let Some(block) = block {
                        for (a, b) in input.iter_mut().zip(block) {
                            *a += b;
                        }
                    }
                }
            }
            let mut ctx = Ctx {
                sr,
                midi: &self.midi,
                audio_in: &self.audio_in,
                master: &mut self.master,
                midi_out: &mut self.midi_out_buf,
            };
            let mut io = Io {
                ins: &node.ins,
                outs: &mut node.outs,
                p: &node.params,
                linked: schedule.linked[slot],
            };
            node.dsp.process(&mut io, &mut ctx, &node.shared.state);
            for out in node.outs.iter_mut() {
                // A runaway feedback loop must not poison the rest of the patch.
                for x in out.iter_mut() {
                    if !x.is_finite() {
                        *x = 0.0;
                    }
                }
            }
            let monitored = match node.monitor {
                (true, i) => node.outs.get(i),
                (false, i) => node.ins.get(i),
            };
            if let Some(block) = monitored {
                node.shared.record(block, sr);
            }
            for (probe, out) in node.shared.probes.iter().zip(&node.outs) {
                probe.store(out[BLOCK - 1].to_bits(), Ordering::Relaxed);
            }
            self.slots[slot] = Some(node);
        }
        self.midi.clear();
        if let Some(out) = self.midi_out.as_mut() {
            for msg in self.midi_out_buf.drain(..) {
                let _ = out.push(msg);
            }
        } else {
            self.midi_out_buf.clear();
        }
        let mut mono = [0.0; BLOCK];
        for (i, m) in mono.iter_mut().enumerate() {
            *m = (self.master[0][i] + self.master[1][i]) * 0.5;
        }
        self.master_shared.record(&mono, sr);
        for (ch, probe) in self.master_shared.probes.iter().enumerate() {
            probe.store(self.master[ch][BLOCK - 1].to_bits(), Ordering::Relaxed);
        }
        self.frames += BLOCK as u64;
    }

    fn read_input(&mut self) {
        let Some(input) = self.input.as_mut() else {
            return;
        };
        // When the input runs ahead (its clock drifts from the output's), skip to the newest
        // audio so the delay never grows.
        let ahead = input.slots() / 2;
        if ahead > BLOCK * 8 {
            let skip = (ahead - BLOCK * 2) * 2;
            if let Ok(chunk) = input.read_chunk(skip) {
                chunk.commit_all();
            }
        }
        for i in 0..BLOCK {
            let (l, r) = match (input.pop(), input.pop()) {
                (Ok(l), Ok(r)) => (l, r),
                _ => (0.0, 0.0),
            };
            self.audio_in[0][i] = l;
            self.audio_in[1][i] = r;
        }
    }

    /// Fills interleaved `out` (any number of channels), running as many blocks as it takes.
    pub fn render(&mut self, out: &mut [f32], channels: usize) {
        let channels = channels.max(1);
        for frame in out.chunks_mut(channels) {
            if self.pending_at >= BLOCK {
                self.block();
                self.pending = self.master;
                self.pending_at = 0;
            }
            let (l, r) = (
                self.pending[0][self.pending_at],
                self.pending[1][self.pending_at],
            );
            self.pending_at += 1;
            match frame.len() {
                1 => frame[0] = (l + r) * 0.5,
                _ => {
                    frame[0] = l;
                    frame[1] = r;
                    for x in &mut frame[2..] {
                        *x = 0.0;
                    }
                }
            }
        }
    }
}
