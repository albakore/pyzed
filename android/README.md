# Android

Pyzed apps as Android apps. The app is a NativeActivity, so the APK has no Java code:
`src/android.rs` is its entry point. It unpacks `pyzed-bundle.zip` from the APK's assets, starts
an embedded Python 3.13 with Pyzed's core built in, and runs the app's `main.py`. The packaging
lives in `python/pyzed/android.py`; projects build with `pyzed build --target android-arm64`
(see the docs page *Building for Android*).

Not on Android yet: file dialogs, the clipboard, audio devices and MIDI.

## Building an APK from this checkout

You need Rust, Java (for signing) and the Android SDK with the NDK, build-tools and a platform:

```bash
sdkmanager "ndk;29.0.14206865" "build-tools;36.0.0" "platforms;android-36" "platform-tools"
export ANDROID_HOME=~/Android/Sdk
python android/build_apk.py android/demo --name "Pyzed demo"
```

The app is a `.py` file or a folder with `main.py` in it (`android/demo` tries the safe area,
the soft keyboard and the back button). The script builds the engine for Android when it is
missing (`--rebuild` builds it again), downloads Python for Android from Maven Central once
(`com.chaquo.python:target`, cached in `~/.cache/pyzed/android`) and writes `dist/<app>.apk`,
signed with the usual debug key (`~/.android/debug.keystore`).

| Option | What it does |
| --- | --- |
| `--name Counter` | The name under the icon. |
| `--package org.example.counter` | The Android package (default `org.pyzed.<app>`). |
| `--version 1.2.0` | The version shown in the system settings. |
| `--icon icon.png` | A square PNG for the launcher. |
| `--abi arm64-v8a --abi x86_64` | The processors: `arm64-v8a` for phones (the default), `x86_64` for an emulator on a PC. |
| `--aab` | An Android App Bundle for Google Play. |
| `--keystore release.jks --key-alias upload` | Sign with a release key (passwords in `PYZED_KEYSTORE_PASSWORD` and `PYZED_KEY_PASSWORD`). |
| `--engine-only` | Only build the engine (`target/<triple>/release/lib_core.so`); the release workflow uploads it. |

## Trying it

```bash
adb install -r dist/demo.apk
adb logcat -s pyzed python.stdout python.stderr RustPanic AndroidRuntime DEBUG
```

The `pyzed` lines show each step of the start (unpacking, starting Python, running the app) and
the error that stopped it; `print` goes to `python.stdout`. The last error is also kept in the
app's files folder: `adb shell run-as org.pyzed.demo cat files/last-error.txt`.

Without `adb`, connect the phone to a computer over USB (file transfer) and open
`Android/data/org.pyzed.demo/files/pyzed-log.txt`: the same lines are written there.

## How it works on the phone

- The window waits for the activity to resume before it opens (Android gives it nothing to draw
  on before that). In the background the windows drop their surfaces, and they get new ones when
  the app comes back (`iced_winit` in Pyzed's fork of Iced).
- Windows keep clear of the system bars, the camera cutout and the soft keyboard: the insets come
  from `WindowInsets` over JNI and are read again every 200 ms (a NativeActivity is not told
  when they change). `safe_area = False` draws under them; `pz.safe_area()` reads them.
- The back button calls `on_back()`; when it returns `False` (or there is none) the app moves to
  the background (`Activity.moveTaskToBack`).

## Checking a bundle without a phone

There is no emulator without KVM, but an Android system image runs Python: take
`system-images;android-28;default;x86_64`, skip the first MiB of `system.img` and `vendor.img`
(`dd bs=1M skip=1`), copy them out with `debugfs -R "rdump / ROOT"`, mount `proc` in `ROOT/proc`
and `chroot ROOT /system/bin/sh`. A small C program built with the NDK that `dlopen`s
`lib_core.so` and calls `pyzed_android_check(files, log)` on the unpacked bundle loads the app
without opening its window.

## What is still to do

- Test on phones and emulators, then fix what the first runs show.
- File dialogs, the clipboard and audio on Android.
