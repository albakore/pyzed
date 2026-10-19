"""Visual regression tests: every scene in ``tests/visual/scenes.py`` is rendered off-screen and compared,
pixel by pixel, with its reference image in ``tests/visual/references``.

When a change to the UI is intended, regenerate the references and commit them::

    pytest tests/test_visual.py --update-snapshots            # every scene that changed
    pytest tests/test_visual.py --update-snapshots -k palette  # only some

A failing comparison writes ``<scene>.actual.png`` and ``<scene>.diff.png`` (changed pixels in red) to
``tests/visual/output``. The references are rendered on Linux with the CPU renderer; on other platforms the
comparisons are skipped unless ``PYZED_VISUAL=1`` is set.
"""

import os
import sys
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image", reason="the visual tests need Pillow (pip install pillow)")
ImageChops = pytest.importorskip("PIL.ImageChops")

sys.path.insert(0, str(Path(__file__).parent / "visual"))
from scenes import SCENES  # noqa: E402

HERE = Path(__file__).parent / "visual"
REFERENCES = HERE / "references"
OUTPUT = HERE / "output"

#: A channel may differ by this much before the pixel counts as changed (antialiasing noise).
TOLERANCE = 16
#: Share of pixels that may change before the test fails.
MAX_CHANGED = 0.0005

pytestmark = [
    pytest.mark.visual,
    pytest.mark.skipif(not sys.platform.startswith("linux") and os.environ.get("PYZED_VISUAL") != "1",
                       reason="reference images are rendered on Linux (set PYZED_VISUAL=1 to compare anyway)"),
]


def compare(actual, expected):
    """Returns ``(changed_pixels, diff_image)``; ``diff_image`` dims the reference and marks changes in red."""
    if actual.size != expected.size:
        return actual.size[0] * actual.size[1], None
    delta = ImageChops.difference(actual.convert("RGBA"), expected.convert("RGBA"))
    mask = Image.new("L", delta.size, 0)
    for band in delta.split():
        mask = ImageChops.lighter(mask, band.point(lambda v: 255 if v > TOLERANCE else 0))
    changed = mask.histogram()[255]
    diff = Image.blend(expected.convert("RGB"), Image.new("RGB", expected.size, "white"), 0.7)
    diff.paste((255, 0, 0), mask=mask)
    return changed, diff


@pytest.mark.parametrize("name", sorted(SCENES))
def test_scene_matches_reference(name, request, tmp_path):
    scene = SCENES[name]
    for old in OUTPUT.glob(f"{name}.*.png"):
        old.unlink()
    shot = tmp_path / f"{name}.png"
    app = scene.build()
    app.screenshot(shot, size=scene.size, scale=1)
    if getattr(app, "errors", None):
        raise app.errors[0]
    reference = REFERENCES / f"{name}.png"
    update = request.config.getoption("--update-snapshots")

    if not reference.exists():
        if update:
            REFERENCES.mkdir(parents=True, exist_ok=True)
            reference.write_bytes(shot.read_bytes())
            return
        pytest.fail(f"no reference image for {name!r}: run pytest tests/test_visual.py --update-snapshots -k {name}")

    with Image.open(shot) as actual, Image.open(reference) as expected:
        actual.load()
        expected.load()
        changed, diff = compare(actual, expected)
        total = expected.size[0] * expected.size[1]
    if changed <= total * MAX_CHANGED:
        return
    if update:
        reference.write_bytes(shot.read_bytes())
        return
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / f"{name}.actual.png").write_bytes(shot.read_bytes())
    if diff is not None:
        diff.save(OUTPUT / f"{name}.diff.png")
    pytest.fail(
        f"{name!r} differs from its reference in {changed} of {total} pixels "
        f"(see tests/visual/output/{name}.diff.png). If the change is intended, run: "
        f"pytest tests/test_visual.py --update-snapshots -k {name}"
    )


def test_every_reference_has_a_scene():
    """A renamed or deleted scene must take its reference image with it."""
    orphans = sorted(p.stem for p in REFERENCES.glob("*.png") if p.stem not in SCENES)
    assert not orphans, f"reference images without a scene in tests/visual/scenes.py: {orphans}"
