//! The catalog of audio modules: their ports and parameters, shared by the engine (to create and
//! patch modules) and by Python (`audio.modules()`, which the rack draws from).

use std::sync::OnceLock;

/// What travels through a port. Every cable carries a mono signal at audio rate, as in VCV Rack;
/// the type only says how to read it: audio (±1), cv (pitch in V/oct, 0 = C4, or a 0..1 amount),
/// gate (0 or 1) or midi.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum PortType {
    Audio,
    Cv,
    Gate,
    /// Reserved for cables of MIDI events; no module has such a port yet.
    #[allow(dead_code)]
    Midi,
}

impl PortType {
    pub fn name(self) -> &'static str {
        match self {
            PortType::Audio => "audio",
            PortType::Cv => "cv",
            PortType::Gate => "gate",
            PortType::Midi => "midi",
        }
    }
}

pub struct PortSpec {
    pub name: String,
    pub label: String,
    pub kind: PortType,
}

pub struct ParamSpec {
    pub name: String,
    pub label: String,
    pub min: f32,
    pub max: f32,
    pub default: f32,
    pub unit: &'static str,
    /// A logarithmic knob (frequencies, times) turns evenly through octaves instead of hertz.
    pub log: bool,
    /// The number of positions of a stepped knob (`None` = continuous).
    pub steps: Option<u32>,
    /// The labels of a choice: the value is the index of the chosen one.
    pub options: Vec<&'static str>,
}

/// Which signal a module shows in its scope, spectrum and level meter.
#[derive(Clone, Copy)]
pub enum Monitor {
    Output(usize),
    Input(usize),
}

pub struct ModuleSpec {
    pub kind: &'static str,
    pub label: &'static str,
    pub category: &'static str,
    pub description: &'static str,
    pub inputs: Vec<PortSpec>,
    pub outputs: Vec<PortSpec>,
    pub params: Vec<ParamSpec>,
    /// Values the module reports while it plays (`node.state`), such as the step of a sequencer.
    pub state: Vec<&'static str>,
    pub monitor: Monitor,
}

impl ModuleSpec {
    pub fn param(&self, name: &str) -> Option<usize> {
        self.params.iter().position(|p| p.name == name)
    }

    pub fn input(&self, name: &str) -> Option<usize> {
        self.inputs.iter().position(|p| p.name == name)
    }

    pub fn output(&self, name: &str) -> Option<usize> {
        self.outputs.iter().position(|p| p.name == name)
    }
}

fn port(name: &str, label: &str, kind: PortType) -> PortSpec {
    PortSpec {
        name: name.into(),
        label: label.into(),
        kind,
    }
}

fn audio(name: &str, label: &str) -> PortSpec {
    port(name, label, PortType::Audio)
}

fn cv(name: &str, label: &str) -> PortSpec {
    port(name, label, PortType::Cv)
}

fn gate(name: &str, label: &str) -> PortSpec {
    port(name, label, PortType::Gate)
}

fn lin(name: &str, label: &str, min: f32, max: f32, default: f32, unit: &'static str) -> ParamSpec {
    ParamSpec {
        name: name.into(),
        label: label.into(),
        min,
        max,
        default,
        unit,
        log: false,
        steps: None,
        options: Vec::new(),
    }
}

fn log(name: &str, label: &str, min: f32, max: f32, default: f32, unit: &'static str) -> ParamSpec {
    ParamSpec {
        log: true,
        ..lin(name, label, min, max, default, unit)
    }
}

fn stepped(
    name: &str,
    label: &str,
    min: f32,
    max: f32,
    default: f32,
    unit: &'static str,
) -> ParamSpec {
    ParamSpec {
        steps: Some((max - min) as u32 + 1),
        ..lin(name, label, min, max, default, unit)
    }
}

fn choice(name: &str, label: &str, options: &[&'static str], default: usize) -> ParamSpec {
    ParamSpec {
        steps: Some(options.len() as u32),
        options: options.to_vec(),
        ..lin(
            name,
            label,
            0.0,
            (options.len() - 1) as f32,
            default as f32,
            "",
        )
    }
}

fn switch(name: &str, label: &str, on: bool) -> ParamSpec {
    choice(name, label, &["off", "on"], on as usize)
}

/// The most steps a sequencer plays.
pub const SEQ_STEPS: usize = 16;

pub const WAVES: &[&str] = &["sine", "triangle", "saw", "square"];

fn build() -> Vec<ModuleSpec> {
    use Monitor::{Input, Output};
    let specs = vec![
        ModuleSpec {
            kind: "oscillator",
            label: "Oscillator",
            category: "Sources",
            description: "A band-limited VCO: sine, triangle, saw and square (with pulse width), \
                          tuned by `freq` plus the V/oct `pitch` input.",
            inputs: vec![
                cv("pitch", "Pitch (V/oct)"),
                cv("fm", "FM"),
                cv("pwm", "PWM"),
                gate("sync", "Sync"),
            ],
            outputs: vec![
                audio("out", "Out"),
                audio("sine", "Sine"),
                audio("triangle", "Triangle"),
                audio("saw", "Saw"),
                audio("square", "Square"),
            ],
            params: vec![
                log("freq", "Frequency", 8.0, 20000.0, 261.63, "Hz"),
                choice("wave", "Wave", WAVES, 2),
                lin("fine", "Fine", -1.0, 1.0, 0.0, "st"),
                lin("pw", "Pulse width", 0.05, 0.95, 0.5, ""),
                lin("fm_amount", "FM amount", 0.0, 1.0, 0.0, ""),
                lin("level", "Level", 0.0, 1.0, 0.8, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "lfo",
            label: "LFO",
            category: "Modulation",
            description: "A slow oscillator to move other parameters: sine, triangle, saw, square \
                          or random steps (sample and hold).",
            inputs: vec![cv("rate", "Rate"), gate("reset", "Reset")],
            outputs: vec![cv("out", "Out"), cv("unipolar", "Unipolar")],
            params: vec![
                log("rate", "Rate", 0.01, 50.0, 1.0, "Hz"),
                choice(
                    "wave",
                    "Wave",
                    &["sine", "triangle", "saw", "square", "random"],
                    0,
                ),
                lin("amount", "Amount", 0.0, 1.0, 1.0, ""),
                lin("offset", "Offset", -1.0, 1.0, 0.0, ""),
            ],
            state: vec!["phase"],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "noise",
            label: "Noise",
            category: "Sources",
            description: "White, pink or brown noise.",
            inputs: vec![],
            outputs: vec![audio("out", "Out")],
            params: vec![
                choice("color", "Color", &["white", "pink", "brown"], 0),
                lin("level", "Level", 0.0, 1.0, 0.5, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "sampler",
            label: "Sampler",
            category: "Sources",
            description: "Plays a WAV file or a list of samples (`node.load`) when its gate opens: \
                          once, while the gate is held or in a loop.",
            inputs: vec![gate("gate", "Gate"), cv("pitch", "Pitch (V/oct)")],
            outputs: vec![audio("left", "Left"), audio("right", "Right")],
            params: vec![
                choice("mode", "Mode", &["one-shot", "gate", "loop"], 0),
                lin("tune", "Tune", -24.0, 24.0, 0.0, "st"),
                lin("start", "Start", 0.0, 1.0, 0.0, ""),
                lin("end", "End", 0.0, 1.0, 1.0, ""),
                lin("level", "Level", 0.0, 1.0, 0.8, ""),
            ],
            state: vec!["position", "playing"],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "drum",
            label: "Drum",
            category: "Sources",
            description: "A synthesized drum voice (kick, snare, hi-hat, clap or tom) struck by \
                          each rising edge of `trigger`.",
            inputs: vec![gate("trigger", "Trigger"), cv("accent", "Accent")],
            outputs: vec![audio("out", "Out")],
            params: vec![
                choice(
                    "sound",
                    "Sound",
                    &["kick", "snare", "hihat", "clap", "tom"],
                    0,
                ),
                lin("tune", "Tune", -12.0, 12.0, 0.0, "st"),
                log("decay", "Decay", 0.02, 2.0, 0.4, "s"),
                lin("tone", "Tone", 0.0, 1.0, 0.5, ""),
                lin("level", "Level", 0.0, 1.0, 0.8, ""),
            ],
            state: vec!["hit"],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "audio_in",
            label: "Audio input",
            category: "I/O",
            description: "The sound of the input device (a microphone or a line in), opened with \
                          `Engine(input_device=...)` or `input=True`.",
            inputs: vec![],
            outputs: vec![audio("left", "Left"), audio("right", "Right")],
            params: vec![lin("gain", "Gain", 0.0, 4.0, 1.0, "")],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "midi_in",
            label: "MIDI to CV",
            category: "I/O",
            description: "Turns the notes of a MIDI keyboard (or `engine.note_on`) into pitch, gate \
                          and velocity, playing the last note held.",
            inputs: vec![],
            outputs: vec![
                cv("pitch", "Pitch (V/oct)"),
                gate("gate", "Gate"),
                cv("velocity", "Velocity"),
                cv("mod", "Mod wheel"),
                gate("retrigger", "Retrigger"),
            ],
            params: vec![
                stepped("channel", "Channel", 0.0, 16.0, 0.0, ""),
                log("glide", "Glide", 0.0001, 2.0, 0.0001, "s"),
                stepped("bend_range", "Bend range", 0.0, 24.0, 2.0, "st"),
            ],
            state: vec!["note", "gate"],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "constant",
            label: "Constant",
            category: "Utilities",
            description: "A fixed voltage, to drive an input from a knob.",
            inputs: vec![],
            outputs: vec![cv("out", "Out")],
            params: vec![lin("value", "Value", -10.0, 10.0, 1.0, "V")],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "clock",
            label: "Clock",
            category: "Sequencing",
            description: "The tempo of a patch: gates at the chosen division of the beat, on each \
                          beat and on each bar.",
            inputs: vec![gate("reset", "Reset")],
            outputs: vec![
                gate("clock", "Clock"),
                gate("beat", "Beat"),
                gate("bar", "Bar"),
            ],
            params: vec![
                lin("bpm", "Tempo", 20.0, 300.0, 120.0, "BPM"),
                choice("division", "Division", &["1/4", "1/8", "1/16", "1/32"], 2),
                lin("swing", "Swing", 0.0, 0.5, 0.0, ""),
                switch("run", "Run", true),
            ],
            state: vec!["tick", "beat"],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "filter",
            label: "Filter",
            category: "Filters",
            description: "A resonant state-variable filter (VCF) with low-pass, high-pass, band-pass \
                          and notch; `cutoff` takes V/oct, so an envelope or LFO sweeps it.",
            inputs: vec![
                audio("in", "In"),
                cv("cutoff", "Cutoff"),
                cv("resonance", "Resonance"),
            ],
            outputs: vec![
                audio("out", "Out"),
                audio("lowpass", "Low-pass"),
                audio("bandpass", "Band-pass"),
                audio("highpass", "High-pass"),
            ],
            params: vec![
                choice(
                    "mode",
                    "Mode",
                    &["lowpass", "highpass", "bandpass", "notch"],
                    0,
                ),
                log("cutoff", "Cutoff", 20.0, 20000.0, 1200.0, "Hz"),
                lin("resonance", "Resonance", 0.0, 1.0, 0.2, ""),
                lin("cv_amount", "CV amount", -1.0, 1.0, 1.0, ""),
                lin("drive", "Drive", 0.0, 1.0, 0.0, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "vca",
            label: "VCA",
            category: "Modulation",
            description: "An amplifier whose gain follows `cv` (an envelope or an LFO); with nothing \
                          on `cv` it is a plain volume.",
            inputs: vec![audio("in", "In"), cv("cv", "CV")],
            outputs: vec![audio("out", "Out")],
            params: vec![
                lin("gain", "Gain", 0.0, 2.0, 1.0, ""),
                choice("response", "Response", &["linear", "exponential"], 0),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "adsr",
            label: "Envelope",
            category: "Modulation",
            description: "An ADSR envelope: rises while the gate opens, settles at sustain and \
                          fades out when it closes.",
            inputs: vec![gate("gate", "Gate"), gate("retrig", "Retrigger")],
            outputs: vec![cv("out", "Out"), cv("inverted", "Inverted")],
            params: vec![
                log("attack", "Attack", 0.001, 10.0, 0.01, "s"),
                log("decay", "Decay", 0.001, 10.0, 0.2, "s"),
                lin("sustain", "Sustain", 0.0, 1.0, 0.7, ""),
                log("release", "Release", 0.001, 10.0, 0.3, "s"),
            ],
            state: vec!["stage", "level"],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "mixer",
            label: "Mixer",
            category: "Mixing",
            description: "Four channels with level and pan into a stereo pair.",
            inputs: (1..=4)
                .map(|i| audio(&format!("in_{i}"), &format!("In {i}")))
                .collect(),
            outputs: vec![audio("left", "Left"), audio("right", "Right")],
            params: (1..=4)
                .map(|i| {
                    lin(
                        &format!("level_{i}"),
                        &format!("Level {i}"),
                        0.0,
                        1.5,
                        0.8,
                        "",
                    )
                })
                .chain(
                    (1..=4)
                        .map(|i| lin(&format!("pan_{i}"), &format!("Pan {i}"), -1.0, 1.0, 0.0, "")),
                )
                .chain([lin("master", "Master", 0.0, 1.5, 1.0, "")])
                .collect(),
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "delay",
            label: "Delay",
            category: "Effects",
            description: "An echo with feedback and a tone control on the repeats.",
            inputs: vec![audio("in", "In"), cv("time", "Time")],
            outputs: vec![audio("out", "Out")],
            params: vec![
                log("time", "Time", 0.001, 2.0, 0.35, "s"),
                lin("feedback", "Feedback", 0.0, 0.98, 0.4, ""),
                log("tone", "Tone", 200.0, 20000.0, 8000.0, "Hz"),
                lin("mix", "Mix", 0.0, 1.0, 0.35, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "reverb",
            label: "Reverb",
            category: "Effects",
            description: "A stereo room (Freeverb): size, damping and width.",
            inputs: vec![audio("left", "Left"), audio("right", "Right")],
            outputs: vec![audio("left", "Left"), audio("right", "Right")],
            params: vec![
                lin("size", "Size", 0.0, 1.0, 0.6, ""),
                lin("damping", "Damping", 0.0, 1.0, 0.4, ""),
                lin("width", "Width", 0.0, 1.0, 1.0, ""),
                lin("mix", "Mix", 0.0, 1.0, 0.3, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "distortion",
            label: "Distortion",
            category: "Effects",
            description: "Drives the signal into a soft or hard clipper, a wavefolder or a fuzz.",
            inputs: vec![audio("in", "In")],
            outputs: vec![audio("out", "Out")],
            params: vec![
                choice("type", "Type", &["soft", "hard", "fold", "fuzz"], 0),
                lin("drive", "Drive", 0.0, 1.0, 0.4, ""),
                log("tone", "Tone", 200.0, 20000.0, 6000.0, "Hz"),
                lin("mix", "Mix", 0.0, 1.0, 1.0, ""),
                lin("level", "Level", 0.0, 1.0, 0.7, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "chorus",
            label: "Chorus",
            category: "Effects",
            description: "A stereo chorus; with feedback and a short delay it becomes a flanger.",
            inputs: vec![audio("in", "In")],
            outputs: vec![audio("left", "Left"), audio("right", "Right")],
            params: vec![
                log("rate", "Rate", 0.05, 5.0, 0.8, "Hz"),
                lin("depth", "Depth", 0.0, 1.0, 0.5, ""),
                log("delay", "Delay", 1.0, 30.0, 12.0, "ms"),
                lin("feedback", "Feedback", 0.0, 0.9, 0.0, ""),
                lin("mix", "Mix", 0.0, 1.0, 0.5, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "bitcrusher",
            label: "Bitcrusher",
            category: "Effects",
            description: "Lo-fi: fewer bits and a lower sample rate.",
            inputs: vec![audio("in", "In")],
            outputs: vec![audio("out", "Out")],
            params: vec![
                stepped("bits", "Bits", 1.0, 16.0, 8.0, "bit"),
                stepped("downsample", "Downsample", 1.0, 32.0, 4.0, "x"),
                lin("mix", "Mix", 0.0, 1.0, 1.0, ""),
            ],
            state: vec![],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "compressor",
            label: "Compressor",
            category: "Effects",
            description: "Evens out the level; a signal on `sidechain` ducks the input instead \
                          (the pumping of dance music).",
            inputs: vec![audio("in", "In"), audio("sidechain", "Sidechain")],
            outputs: vec![audio("out", "Out")],
            params: vec![
                lin("threshold", "Threshold", -60.0, 0.0, -18.0, "dB"),
                lin("ratio", "Ratio", 1.0, 20.0, 4.0, ":1"),
                log("attack", "Attack", 0.1, 100.0, 10.0, "ms"),
                log("release", "Release", 10.0, 1000.0, 120.0, "ms"),
                lin("makeup", "Makeup", 0.0, 24.0, 0.0, "dB"),
            ],
            state: vec!["reduction"],
            monitor: Output(0),
        },
        ModuleSpec {
            kind: "sequencer",
            label: "Sequencer",
            category: "Sequencing",
            description: "Up to 16 steps of pitch and gate, advanced by `clock` (or by its own \
                          `bpm` in sixteenth notes when nothing is on `clock`).",
            inputs: vec![gate("clock", "Clock"), gate("reset", "Reset")],
            outputs: vec![
                cv("pitch", "Pitch (V/oct)"),
                gate("gate", "Gate"),
                gate("trigger", "Trigger"),
            ],
            params: [
                stepped("steps", "Steps", 1.0, SEQ_STEPS as f32, 8.0, ""),
                lin("gate_length", "Gate length", 0.05, 1.0, 0.5, ""),
                lin("bpm", "Tempo", 0.0, 300.0, 120.0, "BPM"),
            ]
            .into_iter()
            .chain((1..=SEQ_STEPS).map(|i| {
                stepped(
                    &format!("pitch_{i}"),
                    &format!("Pitch {i}"),
                    -24.0,
                    24.0,
                    0.0,
                    "st",
                )
            }))
            .chain(
                (1..=SEQ_STEPS).map(|i| switch(&format!("gate_{i}"), &format!("Gate {i}"), true)),
            )
            .collect(),
            state: vec!["step"],
            monitor: Output(1),
        },
        ModuleSpec {
            kind: "scope",
            label: "Scope",
            category: "Utilities",
            description: "Passes its input through untouched, to watch a signal anywhere in a patch.",
            inputs: vec![audio("in", "In")],
            outputs: vec![audio("out", "Out")],
            params: vec![],
            state: vec![],
            monitor: Input(0),
        },
        ModuleSpec {
            kind: "audio_out",
            label: "Audio output",
            category: "I/O",
            description: "The speakers. With nothing on `right`, `left` plays on both sides.",
            inputs: vec![audio("left", "Left"), audio("right", "Right")],
            outputs: vec![],
            params: vec![lin("volume", "Volume", 0.0, 1.0, 0.8, "")],
            state: vec![],
            monitor: Input(0),
        },
        ModuleSpec {
            kind: "midi_out",
            label: "CV to MIDI",
            category: "I/O",
            description: "Plays the notes of a gate and a pitch on a MIDI output \
                          (`engine.open_midi_output`).",
            inputs: vec![
                cv("pitch", "Pitch (V/oct)"),
                gate("gate", "Gate"),
                cv("velocity", "Velocity"),
            ],
            outputs: vec![],
            params: vec![stepped("channel", "Channel", 1.0, 16.0, 1.0, "")],
            state: vec!["note"],
            monitor: Input(1),
        },
    ];
    for spec in &specs {
        for p in &spec.params {
            debug_assert!(
                p.default >= p.min && p.default <= p.max,
                "{}.{}",
                spec.kind,
                p.name
            );
        }
    }
    specs
}

pub fn specs() -> &'static [ModuleSpec] {
    static SPECS: OnceLock<Vec<ModuleSpec>> = OnceLock::new();
    SPECS.get_or_init(build)
}

pub fn find(kind: &str) -> Option<(usize, &'static ModuleSpec)> {
    specs().iter().enumerate().find(|(_, s)| s.kind == kind)
}
