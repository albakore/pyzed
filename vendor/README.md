# Vendored iced renderers

`iced_wgpu` 0.14.0 and `iced_tiny_skia` 0.14.1, copied from crates.io (MIT, © Héctor Ramón
and the iced contributors), with one addition each: **effect layers**. A widget can draw part
of the tree into its own layer group that is composited with a rotation, an opacity, a blur,
a bloom or a blurred backdrop (`src/effect.rs` in each crate). Pyzed's animations and the
`rotate`, `blur`, `backdrop_blur`, `bloom` and `glass` styles use them.

Everything else is unchanged. To update iced, copy the new releases over these folders and
re-apply the changes marked `pyzed:` in the code.
