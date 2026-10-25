//! Serial ports (`pyzed.iot.SerialPort`): the ports this computer has and a connection to one.
//!
//! Python runs the reading loop in a thread of its own; `read` waits up to the port's timeout
//! without the GIL, so the app keeps drawing while a device is quiet. The connection keeps a
//! second handle to the same port for writing, so a write never waits for a read.

use pyo3::prelude::*;

#[cfg(not(target_os = "android"))]
mod imp {
    use pyo3::exceptions::{PyOSError, PyValueError};
    use pyo3::prelude::*;
    use pyo3::types::{PyBytes, PyDict};
    use serialport::{DataBits, FlowControl, Parity, SerialPort, SerialPortType, StopBits};
    use std::io::{Read, Write};
    use std::sync::Mutex;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::time::Duration;

    fn error(err: impl std::fmt::Display) -> PyErr {
        PyOSError::new_err(err.to_string())
    }

    #[cfg(any(target_os = "macos", target_os = "ios"))]
    fn is_not_a_tty(err: &serialport::Error) -> bool {
        let text = err.description.to_ascii_lowercase();
        text.contains("not a typewriter") || text.contains("inappropriate ioctl")
    }

    /// The serial ports of this computer, one dict each: `name` (`COM3`, `/dev/ttyUSB0`...),
    /// `kind` (`usb`, `pci`, `bluetooth` or `unknown`) and, for USB, `vid`, `pid`,
    /// `serial_number`, `manufacturer` and `product`.
    #[pyfunction]
    pub fn serial_ports(py: Python<'_>) -> PyResult<Vec<Bound<'_, PyDict>>> {
        // Listing reads sysfs (Linux), IOKit (macOS) or the registry (Windows): no GIL needed. It
        // panics where /sys/class/tty is missing (some containers), which means no ports.
        let ports = py
            .detach(|| std::panic::catch_unwind(serialport::available_ports))
            .unwrap_or_else(|_| Ok(Vec::new()))
            .map_err(error)?;
        let mut out = Vec::with_capacity(ports.len());
        for port in ports {
            let info = PyDict::new(py);
            info.set_item("name", &port.port_name)?;
            let kind = match &port.port_type {
                SerialPortType::UsbPort(usb) => {
                    info.set_item("vid", usb.vid)?;
                    info.set_item("pid", usb.pid)?;
                    info.set_item("serial_number", usb.serial_number.clone())?;
                    info.set_item("manufacturer", usb.manufacturer.clone())?;
                    info.set_item("product", usb.product.clone())?;
                    "usb"
                }
                SerialPortType::PciPort => "pci",
                SerialPortType::BluetoothPort => "bluetooth",
                SerialPortType::Unknown => "unknown",
            };
            info.set_item("kind", kind)?;
            out.push(info);
        }
        Ok(out)
    }

    /// An open serial port. Made by `SerialConnection(path, baud_rate, ...)`.
    #[pyclass(frozen, module = "pyzed._core")]
    pub struct SerialConnection {
        reader: Mutex<Option<Box<dyn SerialPort>>>,
        writer: Mutex<Option<Box<dyn SerialPort>>>,
        closed: AtomicBool,
        #[pyo3(get)]
        path: String,
    }

    #[pymethods]
    impl SerialConnection {
        #[new]
        #[allow(clippy::too_many_arguments)] // the port's settings, as Python passes them
        #[pyo3(signature = (path, baud_rate = 9600, data_bits = 8, parity = "none", stop_bits = 1.0,
                            flow_control = "none", timeout = 0.05))]
        fn new(
            py: Python<'_>,
            path: String,
            baud_rate: u32,
            data_bits: u8,
            parity: &str,
            stop_bits: f32,
            flow_control: &str,
            timeout: f64,
        ) -> PyResult<Self> {
            let data_bits = match data_bits {
                5 => DataBits::Five,
                6 => DataBits::Six,
                7 => DataBits::Seven,
                8 => DataBits::Eight,
                _ => return Err(PyValueError::new_err("data_bits must be 5, 6, 7 or 8")),
            };
            let parity = match parity.to_ascii_lowercase().as_str() {
                "none" | "n" => Parity::None,
                "odd" | "o" => Parity::Odd,
                "even" | "e" => Parity::Even,
                _ => {
                    return Err(PyValueError::new_err(
                        "parity must be \"none\", \"odd\" or \"even\"",
                    ));
                }
            };
            let stop_bits = if stop_bits >= 2.0 {
                StopBits::Two
            } else {
                StopBits::One
            };
            let flow_control = match flow_control.to_ascii_lowercase().as_str() {
                "none" | "" => FlowControl::None,
                "software" | "xon/xoff" | "xonxoff" => FlowControl::Software,
                "hardware" | "rts/cts" | "rtscts" => FlowControl::Hardware,
                _ => {
                    return Err(PyValueError::new_err(
                        "flow_control must be \"none\", \"software\" or \"hardware\"",
                    ));
                }
            };
            let timeout = Duration::from_secs_f64(timeout.clamp(0.001, 60.0));
            let opened = py.detach(|| {
                let open = |baud_rate| {
                    serialport::new(&path, baud_rate)
                        .data_bits(data_bits)
                        .parity(parity)
                        .stop_bits(stop_bits)
                        .flow_control(flow_control)
                        .timeout(timeout)
                        .open()
                };
                let port = open(baud_rate);
                // macOS sets the speed with an ioctl that pseudo-terminals refuse (ENOTTY, "Not a
                // typewriter"): they have no speed, so open those without one.
                #[cfg(any(target_os = "macos", target_os = "ios"))]
                let port = match port {
                    Err(e) if baud_rate > 0 && is_not_a_tty(&e) => open(0),
                    port => port,
                };
                let port = port?;
                let writer = port.try_clone()?;
                Ok::<_, serialport::Error>((port, writer))
            });
            let (reader, writer) = opened.map_err(error)?;
            Ok(Self {
                reader: Mutex::new(Some(reader)),
                writer: Mutex::new(Some(writer)),
                closed: AtomicBool::new(false),
                path,
            })
        }

        /// Up to `size` bytes, waiting at most the port's timeout: `b""` when nothing came.
        /// Raises `OSError` when the device is gone (unplugged).
        #[pyo3(signature = (size = 4096))]
        fn read<'py>(&self, py: Python<'py>, size: usize) -> PyResult<Bound<'py, PyBytes>> {
            let mut buffer = vec![0u8; size.max(1)];
            let got = py.detach(|| {
                let mut guard = self.reader.lock().unwrap_or_else(|e| e.into_inner());
                let Some(port) = guard.as_mut() else {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::NotConnected,
                        "the port is closed",
                    ));
                };
                match port.read(&mut buffer) {
                    Ok(0) => Err(std::io::Error::new(
                        std::io::ErrorKind::BrokenPipe,
                        "the device was disconnected",
                    )),
                    Ok(n) => Ok(n),
                    Err(e) if e.kind() == std::io::ErrorKind::TimedOut => Ok(0),
                    Err(e) if e.kind() == std::io::ErrorKind::Interrupted => Ok(0),
                    Err(e) => Err(e),
                }
            });
            match got {
                Ok(n) => Ok(PyBytes::new(py, &buffer[..n])),
                Err(e) => Err(error(e)),
            }
        }

        /// Sends `data` and returns how many bytes went out.
        fn write(&self, py: Python<'_>, data: Vec<u8>) -> PyResult<usize> {
            py.detach(|| {
                let mut guard = self.writer.lock().unwrap_or_else(|e| e.into_inner());
                let port = guard.as_mut().ok_or_else(|| {
                    std::io::Error::new(std::io::ErrorKind::NotConnected, "the port is closed")
                })?;
                // No flush: it waits until the device has taken every byte (tcdrain), which never
                // ends on a pseudo-terminal nobody reads yet (macOS) or with flow control held.
                port.write_all(&data)?;
                Ok::<_, std::io::Error>(data.len())
            })
            .map_err(error)
        }

        /// How many received bytes wait to be read.
        fn waiting(&self) -> PyResult<u32> {
            let guard = self.writer.lock().unwrap_or_else(|e| e.into_inner());
            match guard.as_ref() {
                Some(port) => port.bytes_to_read().map_err(error),
                None => Ok(0),
            }
        }

        /// Sets the DTR line (many boards reset when it drops).
        fn set_dtr(&self, level: bool) -> PyResult<()> {
            self.with_writer(|port| port.write_data_terminal_ready(level))
        }

        /// Sets the RTS line.
        fn set_rts(&self, level: bool) -> PyResult<()> {
            self.with_writer(|port| port.write_request_to_send(level))
        }

        /// Changes the speed of an open port.
        fn set_baud_rate(&self, baud_rate: u32) -> PyResult<()> {
            self.with_writer(|port| port.set_baud_rate(baud_rate))
        }

        /// Drops what is waiting to be read and to be sent.
        fn clear(&self) -> PyResult<()> {
            self.with_writer(|port| port.clear(serialport::ClearBuffer::All))
        }

        #[getter]
        fn is_open(&self) -> bool {
            !self.closed.load(Ordering::SeqCst)
        }

        /// Closes the port (a read that is waiting ends within the timeout).
        fn close(&self, py: Python<'_>) {
            self.closed.store(true, Ordering::SeqCst);
            py.detach(|| {
                self.writer.lock().unwrap_or_else(|e| e.into_inner()).take();
                self.reader.lock().unwrap_or_else(|e| e.into_inner()).take();
            });
        }
    }

    impl SerialConnection {
        fn with_writer(
            &self,
            f: impl FnOnce(&mut Box<dyn SerialPort>) -> serialport::Result<()>,
        ) -> PyResult<()> {
            let mut guard = self.writer.lock().unwrap_or_else(|e| e.into_inner());
            match guard.as_mut() {
                Some(port) => f(port).map_err(error),
                None => Err(PyOSError::new_err("the port is closed")),
            }
        }
    }
}

#[cfg(target_os = "android")]
mod imp {
    use pyo3::exceptions::PyOSError;
    use pyo3::prelude::*;
    use pyo3::types::{PyDict, PyTuple};

    /// Android apps reach USB devices through Java's UsbManager, which Pyzed does not wrap yet.
    #[pyfunction]
    pub fn serial_ports(_py: Python<'_>) -> PyResult<Vec<Bound<'_, PyDict>>> {
        Ok(Vec::new())
    }

    #[pyclass(frozen, module = "pyzed._core")]
    pub struct SerialConnection;

    #[pymethods]
    impl SerialConnection {
        #[new]
        #[pyo3(signature = (path, *_args, **_kwargs))]
        fn new(
            path: String,
            _args: &Bound<'_, PyTuple>,
            _kwargs: Option<&Bound<'_, PyDict>>,
        ) -> PyResult<Self> {
            Err(PyOSError::new_err(format!(
                "serial ports are not available on Android ({path})"
            )))
        }
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(imp::serial_ports, m)?)?;
    m.add_class::<imp::SerialConnection>()?;
    Ok(())
}
