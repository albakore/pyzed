//! The signal processing of every module. Each one fills its output blocks from its input blocks
//! and parameters, on the audio thread: no allocation, no locks and no system calls in `process`.

use std::f32::consts::{PI, TAU};
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};

use super::catalog::SEQ_STEPS;

/// The frames processed at once. Small enough that MIDI and parameter changes land within about
/// a millisecond, large enough that the graph's bookkeeping costs nothing next to the signal.
pub const BLOCK: usize = 64;
pub type Block = [f32; BLOCK];

/// A sound loaded into a sampler, one buffer per channel.
pub struct Sample {
    pub channels: Vec<Vec<f32>>,
    pub sample_rate: f32,
}

impl Sample {
    pub fn len(&self) -> usize {
        self.channels.first().map_or(0, Vec::len)
    }
}

/// What a module sees of the world besides its own ports: the sample rate, the MIDI of this
/// block, the input device, the mix that goes to the speakers and the MIDI it sends out.
pub struct Ctx<'a> {
    pub sr: f32,
    pub midi: &'a [[u8; 3]],
    pub audio_in: &'a [Block; 2],
    pub master: &'a mut [Block; 2],
    pub midi_out: &'a mut Vec<[u8; 3]>,
}

pub struct Io<'a> {
    pub ins: &'a [Block],
    pub outs: &'a mut [Block],
    pub p: &'a [f32],
    /// Bit `i` is set when input `i` has a cable.
    pub linked: u64,
}

impl Io<'_> {
    pub fn linked(&self, input: usize) -> bool {
        self.linked & (1 << input) != 0
    }
}

pub fn set_state(state: &[AtomicU32], i: usize, value: f32) {
    if let Some(slot) = state.get(i) {
        slot.store(value.to_bits(), Ordering::Relaxed);
    }
}

pub trait Dsp: Send {
    /// Called on a stopped engine when the sample rate changes (and once at creation): the place
    /// to size delay lines.
    fn reset(&mut self, _sr: f32) {}
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]);
    /// `node.trigger()`: strikes a drum, starts a sample or an envelope.
    fn trigger(&mut self) {}
    /// Gives a sampler its sound and hands back the one it replaces (dropped off the audio thread).
    fn set_sample(&mut self, sample: Option<Arc<Sample>>) -> Option<Arc<Sample>> {
        sample
    }
}

pub fn create(kind: &str, sr: f32) -> Box<dyn Dsp> {
    let mut dsp: Box<dyn Dsp> = match kind {
        "oscillator" => Box::<Oscillator>::default(),
        "lfo" => Box::<Lfo>::default(),
        "noise" => Box::<Noise>::default(),
        "sampler" => Box::<Sampler>::default(),
        "drum" => Box::<Drum>::default(),
        "audio_in" => Box::new(AudioIn),
        "midi_in" => Box::<MidiIn>::default(),
        "constant" => Box::new(Constant),
        "clock" => Box::<Clock>::default(),
        "filter" => Box::<Filter>::default(),
        "vca" => Box::<Vca>::default(),
        "adsr" => Box::<Adsr>::default(),
        "mixer" => Box::<Mixer>::default(),
        "delay" => Box::<Delay>::default(),
        "reverb" => Box::<Reverb>::default(),
        "distortion" => Box::<Distortion>::default(),
        "chorus" => Box::<Chorus>::default(),
        "bitcrusher" => Box::<Bitcrusher>::default(),
        "compressor" => Box::<Compressor>::default(),
        "sequencer" => Box::<Sequencer>::default(),
        "scope" => Box::new(Scope),
        "audio_out" => Box::<AudioOut>::default(),
        "midi_out" => Box::<MidiOut>::default(),
        _ => unreachable!("unknown module {kind}"),
    };
    dsp.reset(sr);
    dsp
}

// ---------------------------------------------------------------------------------------------
// Small building blocks

/// Hertz for a pitch in V/oct around `base`.
fn pitched(base: f32, volts: f32) -> f32 {
    base * volts.exp2()
}

/// A rising edge detector with hysteresis, so a noisy gate does not fire twice.
#[derive(Default, Clone, Copy)]
struct Edge {
    high: bool,
}

impl Edge {
    fn rise(&mut self, x: f32) -> bool {
        if self.high {
            if x < 0.25 {
                self.high = false;
            }
            false
        } else if x >= 0.5 {
            self.high = true;
            true
        } else {
            false
        }
    }
}

/// A parameter glides to its new value over a block, so turning a knob never clicks.
#[derive(Default, Clone, Copy)]
struct Smooth {
    value: f32,
    ready: bool,
}

impl Smooth {
    /// The value at the start of the block and the step per frame toward `target`.
    fn ramp(&mut self, target: f32) -> (f32, f32) {
        if !self.ready {
            self.value = target;
            self.ready = true;
        }
        let start = self.value;
        self.value = target;
        (start, (target - start) / BLOCK as f32)
    }
}

#[derive(Clone, Copy)]
struct Rng(u32);

impl Default for Rng {
    fn default() -> Self {
        Rng(0x9E37_79B9)
    }
}

impl Rng {
    /// A uniform number in -1..1 (xorshift).
    fn next(&mut self) -> f32 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.0 = x;
        (x as f32 / u32::MAX as f32) * 2.0 - 1.0
    }
}

/// tanh, close enough for saturation and much cheaper.
fn soft_clip(x: f32) -> f32 {
    if x > 3.0 {
        1.0
    } else if x < -3.0 {
        -1.0
    } else {
        x * (27.0 + x * x) / (27.0 + 9.0 * x * x)
    }
}

/// The coefficient of a one-pole low-pass at `hz`.
fn one_pole(hz: f32, sr: f32) -> f32 {
    1.0 - (-TAU * hz.min(sr * 0.49) / sr).exp()
}

/// The per-frame multiplier that decays by 60 dB in `seconds`.
fn decay_coef(seconds: f32, sr: f32) -> f32 {
    (-6.9078 / (seconds.max(1e-4) * sr)).exp()
}

/// Removes the aliasing of a hard edge in a naive waveform (PolyBLEP).
fn poly_blep(t: f32, dt: f32) -> f32 {
    if t < dt {
        let t = t / dt;
        t + t - t * t - 1.0
    } else if t > 1.0 - dt {
        let t = (t - 1.0) / dt;
        t * t + t + t + 1.0
    } else {
        0.0
    }
}

/// A delay line that reads between samples.
#[derive(Default)]
struct DelayLine {
    buf: Vec<f32>,
    pos: usize,
}

impl DelayLine {
    fn resize(&mut self, len: usize) {
        self.buf = vec![0.0; len.max(4)];
        self.pos = 0;
    }

    fn write(&mut self, x: f32) {
        self.buf[self.pos] = x;
        self.pos = (self.pos + 1) % self.buf.len();
    }

    /// The sample written `delay` frames ago (at least 1).
    fn read(&self, delay: f32) -> f32 {
        let len = self.buf.len();
        let delay = delay.clamp(1.0, (len - 2) as f32);
        let whole = delay as usize;
        let frac = delay - whole as f32;
        let a = self.buf[(self.pos + len - whole) % len];
        let b = self.buf[(self.pos + len - whole - 1) % len];
        a + (b - a) * frac
    }
}

// ---------------------------------------------------------------------------------------------
// Sources

#[derive(Default)]
struct Oscillator {
    phase: f32,
    sync: Edge,
}

impl Dsp for Oscillator {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, _: &[AtomicU32]) {
        let p = io.p;
        let base = p[0] * (p[2] / 12.0).exp2();
        let wave = p[1] as usize;
        let (pw_param, fm_amount, level) = (p[3], p[4], p[5]);
        let modulated = io.linked(0) || io.linked(1);
        let mut dt = (base / ctx.sr).min(0.45);
        for i in 0..BLOCK {
            if modulated {
                let volts = io.ins[0][i] + io.ins[1][i] * fm_amount * 4.0;
                dt = (pitched(base, volts) / ctx.sr).clamp(0.0, 0.45);
            }
            if io.linked(3) && self.sync.rise(io.ins[3][i]) {
                self.phase = 0.0;
            }
            let t = self.phase;
            let pw = (pw_param + io.ins[2][i] * 0.5).clamp(0.05, 0.95);
            let sine = (TAU * t).sin();
            let triangle = 1.0 - 4.0 * (t - 0.5).abs();
            let saw = 2.0 * t - 1.0 - poly_blep(t, dt);
            let mut square = if t < pw { 1.0 } else { -1.0 };
            square += poly_blep(t, dt) - poly_blep((t - pw + 1.0) % 1.0, dt);
            io.outs[1][i] = sine * level;
            io.outs[2][i] = triangle * level;
            io.outs[3][i] = saw * level;
            io.outs[4][i] = square * level;
            io.outs[0][i] = [sine, triangle, saw, square][wave.min(3)] * level;
            self.phase += dt;
            if self.phase >= 1.0 {
                self.phase -= 1.0;
            }
        }
    }
}

#[derive(Default)]
struct Lfo {
    phase: f32,
    held: f32,
    rng: Rng,
    reset: Edge,
}

impl Dsp for Lfo {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let p = io.p;
        let (wave, amount, offset) = (p[1] as usize, p[2], p[3]);
        for i in 0..BLOCK {
            let rate = if io.linked(0) {
                pitched(p[0], io.ins[0][i])
            } else {
                p[0]
            };
            if io.linked(1) && self.reset.rise(io.ins[1][i]) {
                self.phase = 0.0;
            }
            let t = self.phase;
            let x = match wave {
                0 => (TAU * t).sin(),
                1 => 1.0 - 4.0 * (t - 0.5).abs(),
                2 => 2.0 * t - 1.0,
                3 => {
                    if t < 0.5 {
                        1.0
                    } else {
                        -1.0
                    }
                }
                _ => self.held,
            };
            io.outs[0][i] = x * amount + offset;
            io.outs[1][i] = (x * 0.5 + 0.5) * amount + offset;
            self.phase += rate / ctx.sr;
            if self.phase >= 1.0 {
                self.phase -= 1.0;
                self.held = self.rng.next();
            }
        }
        set_state(state, 0, self.phase);
    }
}

#[derive(Default)]
struct Noise {
    rng: Rng,
    pink: [f32; 7],
    brown: f32,
}

impl Dsp for Noise {
    fn process(&mut self, io: &mut Io, _: &mut Ctx, _: &[AtomicU32]) {
        let (color, level) = (io.p[0] as usize, io.p[1]);
        for i in 0..BLOCK {
            let white = self.rng.next();
            let x = match color {
                0 => white,
                1 => {
                    // Paul Kellet's filter: -3 dB per octave.
                    let b = &mut self.pink;
                    b[0] = 0.99886 * b[0] + white * 0.0555179;
                    b[1] = 0.99332 * b[1] + white * 0.0750759;
                    b[2] = 0.96900 * b[2] + white * 0.153_852;
                    b[3] = 0.86650 * b[3] + white * 0.3104856;
                    b[4] = 0.55000 * b[4] + white * 0.5329522;
                    b[5] = -0.7616 * b[5] - white * 0.0168980;
                    let pink = b.iter().sum::<f32>() + white * 0.5362;
                    b[6] = white * 0.115926;
                    pink * 0.11
                }
                _ => {
                    self.brown = (self.brown + white * 0.02) * 0.998;
                    self.brown * 3.5
                }
            };
            io.outs[0][i] = x * level;
        }
    }
}

#[derive(Default)]
struct Sampler {
    sample: Option<Arc<Sample>>,
    pos: f64,
    playing: bool,
    gate: Edge,
    pending: bool,
}

impl Dsp for Sampler {
    fn trigger(&mut self) {
        self.pending = true;
    }

    fn set_sample(&mut self, sample: Option<Arc<Sample>>) -> Option<Arc<Sample>> {
        self.playing = false;
        std::mem::replace(&mut self.sample, sample)
    }

    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let p = io.p;
        let mode = p[0] as usize;
        let Some(sample) = self.sample.as_ref() else {
            io.outs[0].fill(0.0);
            io.outs[1].fill(0.0);
            return;
        };
        let len = sample.len();
        let start = (p[2] * len as f32) as f64;
        let end = ((p[3] * len as f32) as f64)
            .max(start + 1.0)
            .min(len as f64);
        let base = sample.sample_rate as f64 / ctx.sr as f64 * ((p[1] / 12.0) as f64).exp2();
        let (left, right) = (&sample.channels[0], sample.channels.last().unwrap());
        for i in 0..BLOCK {
            let gate = io.ins[0][i];
            if (io.linked(0) && self.gate.rise(gate)) || std::mem::take(&mut self.pending) {
                self.pos = start;
                self.playing = true;
            }
            // In gate mode the sound stops when the gate closes.
            if mode == 1 && io.linked(0) && !self.gate.high {
                self.playing = false;
            }
            if !self.playing || len == 0 {
                io.outs[0][i] = 0.0;
                io.outs[1][i] = 0.0;
                continue;
            }
            let whole = self.pos as usize;
            let frac = (self.pos - whole as f64) as f32;
            let next = (whole + 1).min(len - 1);
            let at =
                |ch: &Vec<f32>| ch[whole.min(len - 1)] + (ch[next] - ch[whole.min(len - 1)]) * frac;
            io.outs[0][i] = at(left) * p[4];
            io.outs[1][i] = at(right) * p[4];
            let rate = if io.linked(1) {
                base * (io.ins[1][i] as f64).exp2()
            } else {
                base
            };
            self.pos += rate;
            if self.pos >= end {
                if mode == 2 {
                    self.pos = start + (self.pos - end);
                } else {
                    self.playing = false;
                }
            }
        }
        set_state(state, 0, (self.pos / len.max(1) as f64) as f32);
        set_state(state, 1, self.playing as u8 as f32);
    }
}

#[derive(Default)]
struct Drum {
    trigger: Edge,
    pending: bool,
    t: f32,
    active: bool,
    phase: f32,
    accent: f32,
    rng: Rng,
    hp: f32,
    hp_in: f32,
    bp: [f32; 2],
    hits: u32,
}

impl Dsp for Drum {
    fn trigger(&mut self) {
        self.pending = true;
    }

    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let p = io.p;
        let (sound, tune, decay, tone, level) =
            (p[0] as usize, (p[1] / 12.0).exp2(), p[2], p[3], p[4]);
        let dt = 1.0 / ctx.sr;
        for i in 0..BLOCK {
            if (io.linked(0) && self.trigger.rise(io.ins[0][i]))
                || std::mem::take(&mut self.pending)
            {
                self.t = 0.0;
                self.phase = 0.0;
                self.active = true;
                self.accent = if io.linked(1) {
                    1.0 + io.ins[1][i].clamp(0.0, 1.0)
                } else {
                    1.0
                };
                self.hits = self.hits.wrapping_add(1);
            }
            if !self.active {
                io.outs[0][i] = 0.0;
                continue;
            }
            let t = self.t;
            let amp = (-t * 6.9 / decay).exp();
            let noise = self.rng.next();
            let x = match sound {
                // Kick: a sine whose pitch drops fast, with a click at the start.
                0 => {
                    let f = 48.0 * tune * (1.0 + 3.0 * (-t * 40.0).exp());
                    self.phase = (self.phase + f * dt) % 1.0;
                    (TAU * self.phase).sin() * amp + noise * (-t * 600.0).exp() * 0.3 * tone
                }
                // Snare: a short tone under a burst of noise; `tone` balances them.
                1 => {
                    let f = 185.0 * tune * (1.0 + 0.5 * (-t * 60.0).exp());
                    self.phase = (self.phase + f * dt) % 1.0;
                    let body = (TAU * self.phase).sin() * (-t * 6.9 / (decay * 0.4)).exp();
                    body * (1.0 - tone) + noise * amp * (0.4 + tone)
                }
                // Hi-hat: noise through a high-pass, brighter with `tone`.
                2 => {
                    let a = 1.0 - one_pole(3000.0 + 7000.0 * tone, ctx.sr);
                    self.hp = a * (self.hp + noise - self.hp_in);
                    self.hp_in = noise;
                    self.hp * (-t * 6.9 / (decay * 0.25)).exp() * 1.5
                }
                // Clap: three quick bursts of band-passed noise, then a tail.
                3 => {
                    let f = (900.0 + 1200.0 * tone) * tune;
                    let g = (PI * f / ctx.sr).tan();
                    let k = 1.0;
                    let (ic1, ic2) = (self.bp[0], self.bp[1]);
                    let v1 = (ic1 + g * (noise - ic2)) / (1.0 + g * (g + k));
                    let v2 = ic2 + g * v1;
                    self.bp = [2.0 * v1 - ic1, 2.0 * v2 - ic2];
                    let burst = (t * 100.0) % 1.0;
                    let env = if t < 0.03 { (-burst * 8.0).exp() } else { amp };
                    v1 * env * 3.0
                }
                // Tom: a tuned sine with a gentle pitch drop.
                _ => {
                    let f = 110.0 * tune * (1.0 + 0.6 * (-t * 20.0).exp());
                    self.phase = (self.phase + f * dt) % 1.0;
                    (TAU * self.phase).sin() * amp + noise * amp * 0.05 * tone
                }
            };
            io.outs[0][i] = soft_clip(x * self.accent) * level;
            self.t += dt;
            if self.t > decay * 1.2 + 0.05 {
                self.active = false;
            }
        }
        set_state(state, 0, self.hits as f32);
    }
}

struct AudioIn;

impl Dsp for AudioIn {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, _: &[AtomicU32]) {
        let gain = io.p[0];
        for ch in 0..2 {
            for i in 0..BLOCK {
                io.outs[ch][i] = ctx.audio_in[ch][i] * gain;
            }
        }
    }
}

#[derive(Default)]
struct MidiIn {
    held: Vec<u8>,
    velocity: f32,
    modwheel: f32,
    bend: f32,
    pitch: f32,
    retrigger: usize,
}

impl Dsp for MidiIn {
    fn reset(&mut self, _: f32) {
        self.held.reserve(128);
    }

    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let channel = io.p[0] as u8;
        let before = self.held.last().copied();
        for msg in ctx.midi {
            if channel != 0 && msg[0] & 0x0f != channel - 1 {
                continue;
            }
            match (msg[0] & 0xf0, msg[2]) {
                (0x90, v) if v > 0 => {
                    self.held.retain(|&n| n != msg[1]);
                    if self.held.len() < 128 {
                        self.held.push(msg[1]);
                    }
                    self.velocity = v as f32 / 127.0;
                    self.retrigger = BLOCK.min(32);
                }
                (0x80, _) | (0x90, _) => self.held.retain(|&n| n != msg[1]),
                (0xb0, v) if msg[1] == 1 => self.modwheel = v as f32 / 127.0,
                // All notes off.
                (0xb0, _) if msg[1] == 123 => self.held.clear(),
                (0xe0, _) => {
                    let value = ((msg[2] as i32) << 7 | msg[1] as i32) - 8192;
                    self.bend = value as f32 / 8192.0;
                }
                _ => {}
            }
        }
        let note = self.held.last().copied();
        if note != before && note.is_some() && before.is_some() {
            // Legato: a new note while another is held retriggers envelopes that listen.
            self.retrigger = BLOCK.min(32);
        }
        let target =
            note.map_or(self.pitch, |n| (n as f32 - 60.0) / 12.0) + self.bend * io.p[2] / 12.0;
        let glide = io.p[1];
        let coef = if glide <= 0.001 {
            1.0
        } else {
            1.0 - decay_coef(glide, ctx.sr)
        };
        let gate = note.is_some() as u8 as f32;
        for i in 0..BLOCK {
            self.pitch += (target - self.pitch) * coef;
            io.outs[0][i] = self.pitch;
            io.outs[1][i] = gate;
            io.outs[2][i] = self.velocity;
            io.outs[3][i] = self.modwheel;
            // A gap in the gate on retrigger lets a following envelope start over.
            let pulse = i < self.retrigger;
            io.outs[4][i] = pulse as u8 as f32;
            if pulse && before.is_some() && note.is_some() {
                io.outs[1][i] = if i < 2 { 0.0 } else { gate };
            }
        }
        self.retrigger = 0;
        // The pitch holds after release, so the tail of the note keeps its tune.
        if note.is_none() {
            self.pitch = target;
        }
        set_state(state, 0, note.map_or(-1.0, f32::from));
        set_state(state, 1, gate);
    }
}

struct Constant;

impl Dsp for Constant {
    fn process(&mut self, io: &mut Io, _: &mut Ctx, _: &[AtomicU32]) {
        io.outs[0].fill(io.p[0]);
    }
}

#[derive(Default)]
struct Clock {
    phase: f64,
    tick: u64,
    reset: Edge,
}

impl Dsp for Clock {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let p = io.p;
        let per_beat = [1u64, 2, 4, 8][(p[1] as usize).min(3)];
        let swing = p[2] as f64;
        let running = p[3] >= 0.5;
        let ticks_per_sec = p[0] as f64 / 60.0 * per_beat as f64;
        for i in 0..BLOCK {
            if io.linked(0) && self.reset.rise(io.ins[0][i]) {
                self.phase = 0.0;
                self.tick = 0;
            }
            if !running {
                io.outs[0][i] = 0.0;
                io.outs[1][i] = 0.0;
                io.outs[2][i] = 0.0;
                continue;
            }
            // Swing delays every second tick by a share of its length.
            let offset = if self.tick % 2 == 1 { swing } else { 0.0 };
            let within = self.phase - offset;
            let high = (0.0..0.5).contains(&within);
            io.outs[0][i] = high as u8 as f32;
            let beat_high = high && self.tick.is_multiple_of(per_beat);
            io.outs[1][i] = beat_high as u8 as f32;
            io.outs[2][i] = (beat_high && self.tick.is_multiple_of(per_beat * 4)) as u8 as f32;
            self.phase += ticks_per_sec / ctx.sr as f64;
            if self.phase >= 1.0 {
                self.phase -= 1.0;
                self.tick += 1;
            }
        }
        set_state(state, 0, self.tick as f32);
        set_state(state, 1, (self.tick / per_beat) as f32);
    }
}

// ---------------------------------------------------------------------------------------------
// Filters and modulation

/// Andrew Simper's state-variable filter (topology-preserving): stable under fast modulation.
#[derive(Default)]
struct Filter {
    ic1: f32,
    ic2: f32,
}

impl Dsp for Filter {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, _: &[AtomicU32]) {
        let p = io.p;
        let (mode, cutoff, cv_amount) = (p[0] as usize, p[1], p[3]);
        let drive = 1.0 + p[4] * 8.0;
        let nyquist = ctx.sr * 0.49;
        let coefs = |hz: f32, res: f32| {
            let g = (PI * hz.clamp(10.0, nyquist) / ctx.sr).tan();
            let k = 2.0 - 1.98 * res.clamp(0.0, 1.0);
            let a1 = 1.0 / (1.0 + g * (g + k));
            (g, k, a1)
        };
        let modulated = io.linked(1) || io.linked(2);
        let (mut g, mut k, mut a1) = coefs(cutoff, p[2]);
        for i in 0..BLOCK {
            if modulated {
                (g, k, a1) = coefs(
                    pitched(cutoff, io.ins[1][i] * cv_amount * 5.0),
                    p[2] + io.ins[2][i],
                );
            }
            let mut v0 = io.ins[0][i];
            if drive > 1.0 {
                v0 = soft_clip(v0 * drive) / drive.sqrt();
            }
            let a2 = g * a1;
            let a3 = g * a2;
            let v3 = v0 - self.ic2;
            let v1 = a1 * self.ic1 + a2 * v3;
            let v2 = self.ic2 + a2 * self.ic1 + a3 * v3;
            self.ic1 = 2.0 * v1 - self.ic1;
            self.ic2 = 2.0 * v2 - self.ic2;
            let (low, band, high) = (v2, v1, v0 - k * v1 - v2);
            io.outs[1][i] = low;
            io.outs[2][i] = band;
            io.outs[3][i] = high;
            io.outs[0][i] = match mode {
                0 => low,
                1 => high,
                2 => band,
                _ => low + high,
            };
        }
        if !self.ic1.is_finite() || !self.ic2.is_finite() {
            *self = Filter::default();
        }
    }
}

#[derive(Default)]
struct Vca {
    gain: Smooth,
}

impl Dsp for Vca {
    fn process(&mut self, io: &mut Io, _: &mut Ctx, _: &[AtomicU32]) {
        let (mut gain, step) = self.gain.ramp(io.p[0]);
        let exponential = io.p[1] >= 0.5;
        for i in 0..BLOCK {
            let mut amount = if io.linked(1) {
                io.ins[1][i].max(0.0)
            } else {
                1.0
            };
            if exponential {
                amount *= amount;
            }
            io.outs[0][i] = io.ins[0][i] * gain * amount;
            gain += step;
        }
    }
}

#[derive(Default, Clone, Copy, PartialEq)]
enum Stage {
    #[default]
    Idle,
    Attack,
    Decay,
    Sustain,
    Release,
}

#[derive(Default)]
struct Adsr {
    stage: Stage,
    level: f32,
    gate: Edge,
    retrig: Edge,
    /// `node.trigger()` holds the gate through attack and decay.
    triggered: bool,
}

impl Dsp for Adsr {
    fn trigger(&mut self) {
        self.stage = Stage::Attack;
        self.triggered = true;
    }

    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let p = io.p;
        let attack = 1.0 / (p[0].max(1e-4) * ctx.sr);
        let decay = decay_coef(p[1], ctx.sr);
        let sustain = p[2];
        let release = decay_coef(p[3], ctx.sr);
        for i in 0..BLOCK {
            let gate = io.ins[0][i];
            let rose = self.gate.rise(gate);
            if rose || (io.linked(1) && self.retrig.rise(io.ins[1][i])) {
                self.stage = Stage::Attack;
                self.triggered = false;
            }
            let held = self.gate.high || (self.triggered && self.stage != Stage::Sustain);
            if !held && self.stage != Stage::Idle && self.stage != Stage::Release {
                self.stage = Stage::Release;
                self.triggered = false;
            }
            match self.stage {
                Stage::Idle => self.level = 0.0,
                Stage::Attack => {
                    self.level += attack;
                    if self.level >= 1.0 {
                        self.level = 1.0;
                        self.stage = Stage::Decay;
                    }
                }
                Stage::Decay => {
                    self.level = sustain + (self.level - sustain) * decay;
                    if (self.level - sustain).abs() < 1e-4 {
                        self.level = sustain;
                        self.stage = Stage::Sustain;
                    }
                }
                Stage::Sustain => self.level = sustain,
                Stage::Release => {
                    self.level *= release;
                    if self.level < 1e-5 {
                        self.level = 0.0;
                        self.stage = Stage::Idle;
                    }
                }
            }
            io.outs[0][i] = self.level;
            io.outs[1][i] = 1.0 - self.level;
        }
        set_state(state, 0, self.stage as u8 as f32);
        set_state(state, 1, self.level);
    }
}

#[derive(Default)]
struct Mixer {
    gains: [Smooth; 8],
}

impl Dsp for Mixer {
    fn process(&mut self, io: &mut Io, _: &mut Ctx, _: &[AtomicU32]) {
        io.outs[0].fill(0.0);
        io.outs[1].fill(0.0);
        let master = io.p[8];
        for ch in 0..4 {
            // Equal-power panning keeps the loudness as a sound moves across.
            let angle = (io.p[4 + ch].clamp(-1.0, 1.0) + 1.0) * PI / 4.0;
            let level = io.p[ch] * master;
            let (mut l, l_step) = self.gains[ch * 2].ramp(level * angle.cos());
            let (mut r, r_step) = self.gains[ch * 2 + 1].ramp(level * angle.sin());
            if !io.linked(ch) {
                continue;
            }
            for i in 0..BLOCK {
                let x = io.ins[ch][i];
                io.outs[0][i] += x * l;
                io.outs[1][i] += x * r;
                l += l_step;
                r += r_step;
            }
        }
    }
}

// ---------------------------------------------------------------------------------------------
// Effects

#[derive(Default)]
struct Delay {
    line: DelayLine,
    time: f32,
    tone: f32,
    mix: Smooth,
}

impl Dsp for Delay {
    fn reset(&mut self, sr: f32) {
        self.line.resize((sr * 2.1) as usize + 8);
        self.time = 0.0;
    }

    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, _: &[AtomicU32]) {
        let p = io.p;
        let feedback = p[1];
        let tone = one_pole(p[2], ctx.sr);
        let (mut mix, mix_step) = self.mix.ramp(p[3]);
        let max = (self.line.buf.len() - 3) as f32;
        // The time glides, so turning the knob bends the pitch of the echo instead of clicking.
        let glide = 1.0 - (-1.0 / (0.05 * ctx.sr)).exp();
        if self.time == 0.0 {
            self.time = p[0] * ctx.sr;
        }
        for i in 0..BLOCK {
            let seconds = if io.linked(1) {
                p[0] * io.ins[1][i].exp2()
            } else {
                p[0]
            };
            let target = (seconds * ctx.sr).clamp(1.0, max);
            self.time += (target - self.time) * glide;
            let x = io.ins[0][i];
            let wet = self.line.read(self.time);
            self.tone += (wet - self.tone) * tone;
            self.line.write(x + self.tone * feedback + 1e-20);
            io.outs[0][i] = x * (1.0 - mix) + wet * mix;
            mix += mix_step;
        }
    }
}

/// One of Freeverb's comb filters.
#[derive(Default)]
struct Comb {
    buf: Vec<f32>,
    pos: usize,
    store: f32,
}

impl Comb {
    fn process(&mut self, x: f32, feedback: f32, damp: f32) -> f32 {
        let out = self.buf[self.pos];
        self.store = out * (1.0 - damp) + self.store * damp + 1e-20;
        self.buf[self.pos] = x + self.store * feedback;
        self.pos = (self.pos + 1) % self.buf.len();
        out
    }
}

#[derive(Default)]
struct Allpass {
    buf: Vec<f32>,
    pos: usize,
}

impl Allpass {
    fn process(&mut self, x: f32) -> f32 {
        let delayed = self.buf[self.pos];
        let out = delayed - x;
        self.buf[self.pos] = x + delayed * 0.5;
        self.pos = (self.pos + 1) % self.buf.len();
        out
    }
}

#[derive(Default)]
struct Reverb {
    combs: [Vec<Comb>; 2],
    allpasses: [Vec<Allpass>; 2],
    mix: Smooth,
}

impl Dsp for Reverb {
    fn reset(&mut self, sr: f32) {
        const COMBS: [usize; 8] = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617];
        const ALLPASSES: [usize; 4] = [556, 441, 341, 225];
        const SPREAD: usize = 23;
        let scale = sr / 44100.0;
        for ch in 0..2 {
            let extra = ch * SPREAD;
            self.combs[ch] = COMBS
                .iter()
                .map(|&n| Comb {
                    buf: vec![0.0; (((n + extra) as f32) * scale) as usize + 1],
                    ..Comb::default()
                })
                .collect();
            self.allpasses[ch] = ALLPASSES
                .iter()
                .map(|&n| Allpass {
                    buf: vec![0.0; (((n + extra) as f32) * scale) as usize + 1],
                    pos: 0,
                })
                .collect();
        }
    }

    fn process(&mut self, io: &mut Io, _: &mut Ctx, _: &[AtomicU32]) {
        let p = io.p;
        let feedback = 0.7 + p[0] * 0.28;
        let damp = p[1] * 0.4;
        let width = p[2];
        let (wet1, wet2) = (width / 2.0 + 0.5, (1.0 - width) / 2.0);
        let (mut mix, step) = self.mix.ramp(p[3]);
        let stereo = io.linked(1);
        for i in 0..BLOCK {
            let l = io.ins[0][i];
            let r = if stereo { io.ins[1][i] } else { l };
            let input = (l + r) * 0.015;
            let mut out = [0.0f32; 2];
            for ((acc, combs), allpasses) in
                out.iter_mut().zip(&mut self.combs).zip(&mut self.allpasses)
            {
                for comb in combs {
                    *acc += comb.process(input, feedback, damp);
                }
                for allpass in allpasses {
                    *acc = allpass.process(*acc);
                }
            }
            let wet_l = out[0] * wet1 + out[1] * wet2;
            let wet_r = out[1] * wet1 + out[0] * wet2;
            io.outs[0][i] = l * (1.0 - mix) + wet_l * mix;
            io.outs[1][i] = r * (1.0 - mix) + wet_r * mix;
            mix += step;
        }
    }
}

#[derive(Default)]
struct Distortion {
    tone: f32,
}

impl Dsp for Distortion {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, _: &[AtomicU32]) {
        let p = io.p;
        let kind = p[0] as usize;
        let gain = 1.0 + p[1] * p[1] * 60.0;
        let tone = one_pole(p[2], ctx.sr);
        let (mix, level) = (p[3], p[4]);
        for i in 0..BLOCK {
            let x = io.ins[0][i];
            let driven = x * gain;
            let y = match kind {
                0 => soft_clip(driven),
                1 => driven.clamp(-1.0, 1.0),
                // A wavefolder reflects the peaks back down instead of flattening them.
                2 => {
                    let t = (driven + 1.0).rem_euclid(4.0);
                    if t < 2.0 { t - 1.0 } else { 3.0 - t }
                }
                _ => {
                    let rectified = if driven > 0.0 { driven } else { driven * 0.3 };
                    soft_clip(rectified * 1.5) - 0.1
                }
            };
            self.tone += (y - self.tone) * tone;
            io.outs[0][i] = (x * (1.0 - mix) + self.tone * mix) * level;
        }
    }
}

#[derive(Default)]
struct Chorus {
    line: DelayLine,
    phase: f32,
    last: f32,
}

impl Dsp for Chorus {
    fn reset(&mut self, sr: f32) {
        self.line.resize((sr * 0.08) as usize + 8);
    }

    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, _: &[AtomicU32]) {
        let p = io.p;
        let (rate, depth, base, feedback, mix) = (p[0], p[1], p[2], p[3], p[4]);
        let ms = ctx.sr / 1000.0;
        for i in 0..BLOCK {
            let x = io.ins[0][i];
            self.line.write(x + self.last * feedback);
            let swing = depth * base * 0.9;
            let left = self
                .line
                .read((base + swing * (TAU * self.phase).sin()) * ms);
            let right = self
                .line
                .read((base + swing * (TAU * (self.phase + 0.25)).sin()) * ms);
            self.last = left;
            io.outs[0][i] = x * (1.0 - mix) + left * mix;
            io.outs[1][i] = x * (1.0 - mix) + right * mix;
            self.phase = (self.phase + rate / ctx.sr) % 1.0;
        }
    }
}

#[derive(Default)]
struct Bitcrusher {
    held: f32,
    count: u32,
}

impl Dsp for Bitcrusher {
    fn process(&mut self, io: &mut Io, _: &mut Ctx, _: &[AtomicU32]) {
        let levels = (p_bits(io.p[0]) - 1.0).max(1.0);
        let every = io.p[1].max(1.0) as u32;
        let mix = io.p[2];
        for i in 0..BLOCK {
            let x = io.ins[0][i];
            if self.count == 0 {
                self.held = ((x * 0.5 + 0.5) * levels).round() / levels * 2.0 - 1.0;
            }
            self.count = (self.count + 1) % every;
            io.outs[0][i] = x * (1.0 - mix) + self.held * mix;
        }
    }
}

fn p_bits(bits: f32) -> f32 {
    (bits.clamp(1.0, 16.0)).exp2()
}

#[derive(Default)]
struct Compressor {
    envelope: f32,
    gain_db: f32,
}

impl Dsp for Compressor {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let p = io.p;
        let (threshold, ratio, makeup) = (p[0], p[1].max(1.0), p[4]);
        let attack = 1.0 - (-1.0 / (p[2] * 0.001 * ctx.sr)).exp();
        let release = 1.0 - (-1.0 / (p[3] * 0.001 * ctx.sr)).exp();
        let sidechain = io.linked(1);
        for i in 0..BLOCK {
            let x = io.ins[0][i];
            let key = if sidechain { io.ins[1][i] } else { x }.abs();
            let coef = if key > self.envelope { attack } else { release };
            self.envelope += (key - self.envelope) * coef;
            let level_db = 20.0 * self.envelope.max(1e-6).log10();
            let over = level_db - threshold;
            let target = if over > 0.0 {
                -over * (1.0 - 1.0 / ratio)
            } else {
                0.0
            };
            self.gain_db += (target - self.gain_db) * coef;
            io.outs[0][i] = x * 10f32.powf((self.gain_db + makeup) / 20.0);
        }
        set_state(state, 0, self.gain_db);
    }
}

// ---------------------------------------------------------------------------------------------
// Sequencing

#[derive(Default)]
struct Sequencer {
    step: usize,
    started: bool,
    clock: Edge,
    reset: Edge,
    /// Frames since the last step, and the length of the last step (to size the gate).
    since: u32,
    period: u32,
    internal: f64,
}

impl Dsp for Sequencer {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let p = io.p;
        let steps = (p[0] as usize).clamp(1, SEQ_STEPS);
        let gate_length = p[1];
        let internal_rate = p[2] as f64 / 60.0 * 4.0 / ctx.sr as f64;
        let external = io.linked(0);
        for i in 0..BLOCK {
            if io.linked(1) && self.reset.rise(io.ins[1][i]) {
                self.step = 0;
                self.started = false;
            }
            let tick = if external {
                self.clock.rise(io.ins[0][i])
            } else if internal_rate > 0.0 {
                self.internal += internal_rate;
                let tick = self.internal >= 1.0 || !self.started;
                if self.internal >= 1.0 {
                    self.internal -= 1.0;
                }
                tick
            } else {
                false
            };
            if tick {
                if self.started {
                    self.step = (self.step + 1) % steps;
                } else {
                    self.started = true;
                }
                if !external {
                    self.period = (1.0 / internal_rate.max(1e-9)) as u32;
                } else if self.since > 0 {
                    self.period = self.since;
                }
                self.since = 0;
            }
            if self.step >= steps {
                self.step = 0;
            }
            let on = p[3 + SEQ_STEPS + self.step] >= 0.5;
            let length = (self.period.max(1) as f32 * gate_length) as u32;
            io.outs[0][i] = p[3 + self.step] / 12.0;
            io.outs[1][i] = (self.started && on && self.since < length.max(1)) as u8 as f32;
            io.outs[2][i] =
                (self.started && on && self.since < (ctx.sr * 0.002) as u32) as u8 as f32;
            self.since = self.since.saturating_add(1);
        }
        set_state(state, 0, self.step as f32);
    }
}

// ---------------------------------------------------------------------------------------------
// Utilities and I/O

struct Scope;

impl Dsp for Scope {
    fn process(&mut self, io: &mut Io, _: &mut Ctx, _: &[AtomicU32]) {
        io.outs[0] = io.ins[0];
    }
}

#[derive(Default)]
struct AudioOut {
    volume: Smooth,
}

impl Dsp for AudioOut {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, _: &[AtomicU32]) {
        let (mut volume, step) = self.volume.ramp(io.p[0]);
        let right = if io.linked(1) { 1 } else { 0 };
        for i in 0..BLOCK {
            ctx.master[0][i] += io.ins[0][i] * volume;
            ctx.master[1][i] += io.ins[right][i] * volume;
            volume += step;
        }
    }
}

#[derive(Default)]
struct MidiOut {
    gate: Edge,
    note: Option<u8>,
}

impl Dsp for MidiOut {
    fn process(&mut self, io: &mut Io, ctx: &mut Ctx, state: &[AtomicU32]) {
        let channel = (io.p[0].clamp(1.0, 16.0) as u8) - 1;
        for i in 0..BLOCK {
            let rose = self.gate.rise(io.ins[1][i]);
            let note = (60.0 + io.ins[0][i] * 12.0).round().clamp(0.0, 127.0) as u8;
            let velocity = if io.linked(2) {
                (io.ins[2][i] * 127.0).round().clamp(1.0, 127.0) as u8
            } else {
                100
            };
            let changed = self.gate.high && self.note.is_some_and(|n| n != note);
            if let Some(old) = self.note
                && (!self.gate.high || changed || rose)
            {
                push_midi(ctx, [0x80 | channel, old, 0]);
                self.note = None;
            }
            if self.gate.high && self.note.is_none() {
                push_midi(ctx, [0x90 | channel, note, velocity]);
                self.note = Some(note);
            }
        }
        set_state(state, 0, self.note.map_or(-1.0, f32::from));
    }
}

fn push_midi(ctx: &mut Ctx, msg: [u8; 3]) {
    // The vector is reserved up front: past its capacity a message is dropped, never allocated.
    if ctx.midi_out.len() < ctx.midi_out.capacity() {
        ctx.midi_out.push(msg);
    }
}
