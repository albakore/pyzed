---
title: Stability and known limitations
description: What Pyzed 1.x promises about its API, how features are deprecated, and what it does not do yet.
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
| Accessibility | No screen reader support yet, and focus moves between fields only from code (`Command.focus`), not with Tab. |
| Effects | `glass`, `bloom` and `glow` are drawn with gradients and shadows: nothing behind a panel is blurred. |
| Animations | 11 properties can be animated (opacity, position, scale, colors, radius, border width and glow); size, rotation and padding cannot. |
| Large data | Virtual lists and tables need rows of the same height. Every update still calls `view()`; [`@pz.memo`](/pyzed/guides/performance/) skips the subtrees that did not change. |
| Text input | The code editor has no input method (IME) support for Chinese, Japanese or Korean; `text_input` does. |
| Platforms | Wheels need glibc 2.28 or newer on Linux; there are no musllinux (Alpine) wheels. Pyzed Design builds are not signed yet. |
| Python | Free-threaded Python (3.13t, 3.14t) is not supported. The `agents` and `mcp` extras need Python 3.10 or newer. |
