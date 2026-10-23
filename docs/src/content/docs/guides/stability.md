---
title: Stability and known limitations
description: "What Pyzed 1.x promises about its Python API, how features are deprecated over releases, and what the framework does not do yet."
sidebar:
  order: 30
---

## Versioning

From 1.0.0 on, Pyzed follows [semantic versioning](https://semver.org/):

- **Patch** releases (`1.0.x`) only fix bugs.
- **Minor** releases (`1.x.0`) add features and never break code that uses the public API.
- **Major** releases (`2.0.0`) are the only ones that can remove or change public API.

The public API is everything documented in the [API reference](/pyzed/reference/app/) and in these guides. Names
that start with an underscore, and anything under `pyzed.designer`, are internal and may change in any release.

`pyzed.agents`, `pyzed.mcp` and the animation API are **provisional** in 1.x: they follow the same rules, but a
minor release may still adjust details that turn out wrong, and the change is always listed under *Breaking
Changes* in the [release notes](/pyzed/changelog/).

## Deprecations

Before public API is removed, it keeps working for at least one minor release and warns with a
`DeprecationWarning` that names its replacement. The removal happens in the next major release.

Pyzed Design files (`.pzform` and components) carry a format version. Pyzed opens files of its own version and
older ones, and refuses a file saved by a newer Pyzed instead of silently dropping what it does not know.

## Known limitations

| Area | Limitation |
| --- | --- |
| Accessibility | No screen reader support yet: Iced does not expose accessibility information. The keyboard works (Tab moves between fields, see [Accessibility](/pyzed/guides/accessibility/)). |
| Effects | With the GPU renderer, shadows are not drawn under boxes filled with a gradient. |
| Animations | 17 properties can be animated (opacity, position, scale, rotation, blur, colors, radius, border width, glow, size, padding and font size); any other style property changes at once. |
| Large data | Virtual lists and tables need rows of the same height. Every update still calls `view()`; [`@pz.memo`](/pyzed/guides/performance/) skips the subtrees that did not change. |
| Platforms | Linux wheels need glibc 2.28 or newer, or musl (Alpine), where the audio engine has no sound devices. Pyzed Design builds are not signed yet. Android is a prototype (`android/build_apk.py`); iOS and the browser are not targets yet. |
| Python | Free-threaded Python (3.13t, 3.14t) is not supported. Pyzed needs Python 3.10 or newer. |
