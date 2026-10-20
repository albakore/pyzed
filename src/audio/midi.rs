//! MIDI devices: keyboards and controllers in, synthesizers and DAWs out (CoreMIDI, WinMM and
//! ALSA sequencer through midir). On Linux and macOS Pyzed can also appear as a virtual port that
//! other programs connect to.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use midir::{MidiInput, MidiInputConnection, MidiOutput, MidiOutputConnection};
use rtrb::{Consumer, Producer};

const CLIENT: &str = "Pyzed";

pub fn inputs() -> Result<Vec<String>, String> {
    let midi = MidiInput::new(CLIENT).map_err(|e| e.to_string())?;
    Ok(midi
        .ports()
        .iter()
        .filter_map(|p| midi.port_name(p).ok())
        .collect())
}

pub fn outputs() -> Result<Vec<String>, String> {
    let midi = MidiOutput::new(CLIENT).map_err(|e| e.to_string())?;
    Ok(midi
        .ports()
        .iter()
        .filter_map(|p| midi.port_name(p).ok())
        .collect())
}

/// Finds a port whose name contains `name` (case-insensitive), or the first one.
fn pick<P>(
    ports: Vec<P>,
    names: Vec<String>,
    name: Option<&str>,
    which: &str,
) -> Result<(P, String), String> {
    let found = ports.into_iter().zip(names).find(|(_, n)| match name {
        Some(name) => n.to_lowercase().contains(&name.to_lowercase()),
        None => true,
    });
    found.ok_or_else(|| match name {
        Some(name) => format!("no MIDI {which} named {name:?}"),
        None => format!("this system has no MIDI {which}"),
    })
}

/// Opens an input port (or a virtual one named `virtual_name`) that feeds `sink`.
pub fn open_input(
    name: Option<&str>,
    virtual_name: Option<&str>,
    sink: Arc<Mutex<Producer<[u8; 3]>>>,
) -> Result<(MidiInputConnection<()>, String), String> {
    let midi = MidiInput::new(CLIENT).map_err(|e| e.to_string())?;
    let callback = move |_: u64, msg: &[u8], _: &mut ()| {
        // Channel messages only: notes, controllers, pitch bend, aftertouch.
        if msg.is_empty() || msg[0] < 0x80 || msg[0] >= 0xf0 {
            return;
        }
        let event = [msg[0], *msg.get(1).unwrap_or(&0), *msg.get(2).unwrap_or(&0)];
        if let Ok(mut sink) = sink.lock() {
            let _ = sink.push(event);
        }
    };
    if let Some(virtual_name) = virtual_name {
        #[cfg(unix)]
        {
            use midir::os::unix::VirtualInput;
            let conn = midi
                .create_virtual(virtual_name, callback, ())
                .map_err(|e| e.to_string())?;
            return Ok((conn, virtual_name.to_string()));
        }
        #[cfg(not(unix))]
        return Err(
            "virtual MIDI ports need Linux or macOS (on Windows, loopMIDI makes one)".into(),
        );
    }
    let ports = midi.ports();
    let names = ports
        .iter()
        .map(|p| midi.port_name(p).unwrap_or_default())
        .collect();
    let (port, port_name) = pick(ports, names, name, "input")?;
    let conn = midi
        .connect(&port, "pyzed-in", callback, ())
        .map_err(|e| e.to_string())?;
    Ok((conn, port_name))
}

/// A MIDI output and the thread that sends it what the `midi_out` modules play.
pub struct Output {
    pub name: String,
    pub conn: Arc<Mutex<MidiOutputConnection>>,
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<Consumer<[u8; 3]>>>,
}

impl Output {
    pub fn open(
        name: Option<&str>,
        virtual_name: Option<&str>,
        mut events: Consumer<[u8; 3]>,
    ) -> Result<Self, (String, Consumer<[u8; 3]>)> {
        let opened = (|| {
            let midi = MidiOutput::new(CLIENT).map_err(|e| e.to_string())?;
            if let Some(virtual_name) = virtual_name {
                #[cfg(unix)]
                {
                    use midir::os::unix::VirtualOutput;
                    let conn = midi
                        .create_virtual(virtual_name)
                        .map_err(|e| e.to_string())?;
                    return Ok((conn, virtual_name.to_string()));
                }
                #[cfg(not(unix))]
                return Err(
                    "virtual MIDI ports need Linux or macOS (on Windows, loopMIDI makes one)"
                        .to_string(),
                );
            }
            let ports = midi.ports();
            let names = ports
                .iter()
                .map(|p| midi.port_name(p).unwrap_or_default())
                .collect();
            let (port, port_name) = pick(ports, names, name, "output")?;
            let conn = midi
                .connect(&port, "pyzed-out")
                .map_err(|e| e.to_string())?;
            Ok::<_, String>((conn, port_name))
        })();
        let (conn, name) = match opened {
            Ok(opened) => opened,
            Err(error) => return Err((error, events)),
        };
        // Whatever the patch played while no port was open is stale.
        while events.pop().is_ok() {}
        let conn = Arc::new(Mutex::new(conn));
        let stop = Arc::new(AtomicBool::new(false));
        let handle = {
            let (conn, stop) = (conn.clone(), stop.clone());
            std::thread::Builder::new()
                .name("pyzed-midi-out".into())
                .spawn(move || {
                    while !stop.load(Ordering::Relaxed) {
                        while let Ok(msg) = events.pop() {
                            if let Ok(mut conn) = conn.lock() {
                                let _ = conn.send(&msg);
                            }
                        }
                        std::thread::sleep(Duration::from_millis(1));
                    }
                    events
                })
                .expect("start the MIDI thread")
        };
        Ok(Output {
            name,
            conn,
            stop,
            handle: Some(handle),
        })
    }

    pub fn send(&self, msg: &[u8]) -> Result<(), String> {
        let mut conn = self.conn.lock().map_err(|_| "the MIDI output is broken")?;
        conn.send(msg).map_err(|e| e.to_string())
    }

    /// Closes the port and hands back the queue of the patch's MIDI.
    pub fn close(mut self) -> Option<Consumer<[u8; 3]>> {
        self.stop.store(true, Ordering::Relaxed);
        self.handle.take().and_then(|h| h.join().ok())
    }
}
