# Android prototype

Work in progress: Pyzed apps as Android apps. The app is a NativeActivity, so the APK has no Java
code: `src/android.rs` is its entry point. It unpacks `pyzed-bundle.zip` from the APK's assets,
starts an embedded Python 3.13 with Pyzed's core built in, and runs the app's `main.py`.

Not on Android yet: file dialogs, the clipboard, audio devices and MIDI. The soft keyboard and
the system back button are untested.

## Building an APK

You need Rust, Java (for signing) and the Android SDK with the NDK, build-tools and a platform:

```bash
sdkmanager "ndk;29.0.14206865" "build-tools;36.0.0" "platforms;android-35" "platform-tools"
export ANDROID_HOME=~/Android/Sdk
python android/build_apk.py examples/counter.py
```

The app is a `.py` file or a folder with `main.py` in it. The script builds the engine for
Android when it is missing (`--rebuild` builds it again), downloads Python for Android from Maven
Central once (`com.chaquo.python:target`, cached in `~/.cache/pyzed/android`) and writes
`dist/<app>.apk`, signed with the usual debug key (`~/.android/debug.keystore`).

| Option | What it does |
| --- | --- |
| `--name Counter` | The name under the icon. |
| `--package org.example.counter` | The Android package (default `org.pyzed.<app>`). |
| `--version 1.2.0` | The version shown in the system settings. |
| `--icon icon.png` | A square PNG for the launcher. |
| `--abi arm64-v8a --abi x86_64` | The processors: `arm64-v8a` for phones (the default), `x86_64` for an emulator on a PC. |

## Trying it

```bash
adb install -r dist/counter.apk
adb logcat -s python.stdout python.stderr
```

`print` and Python errors go to the log. When the app closes at start, the traceback is also
in the app's files folder: `adb shell run-as org.pyzed.counter cat files/last-error.txt`.

## What is still to do

- Test on phones and emulators, then fix what the first runs show.
- Safe areas, the soft keyboard and the back button.
- `pyzed build --target android-arm64` and an Android entry in the editor's Export dialog.
- Release signing with the app's own key, and an AAB for the Play Store.
