//! `audio_devices`: the audio engine reaches sound cards and MIDI (always, except on Linux
//! without the `alsa` feature, which needs ALSA's development files).

fn main() {
    println!("cargo::rustc-check-cfg=cfg(audio_devices)");
    let linux = std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("linux");
    if !linux || std::env::var_os("CARGO_FEATURE_ALSA").is_some() {
        println!("cargo::rustc-cfg=audio_devices");
    } else {
        println!(
            "cargo::warning=built without audio devices or MIDI (pyzed.audio renders offline and \
             on the silent clock only); for sound, install libasound2-dev and pkg-config and \
             build with --features alsa"
        );
    }
}
