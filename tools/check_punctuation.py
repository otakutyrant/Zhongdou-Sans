#!/usr/bin/env python3
"""Validate every encoded punctuation glyph and render focused specimens."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import unicodedata
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


WEIGHTS = (250, 400, 900)
EXPECTED_PUNCTUATION_COUNT = 98
EXTRA_PUNCTUATION = {0x22EF}  # MIDLINE HORIZONTAL ELLIPSIS is category Sm.

REQUIRED_CODEPOINTS = {
    0x2014,
    0x2026,
    0x22EF,
    0x2E3A,
    0x3001,
    0x3002,
    0x300C,
    0x300D,
    0x300E,
    0x300F,
    0x3014,
    0x3015,
    0x30FB,
    0xFF01,
    0xFF0C,
    0xFF1A,
    0xFF1B,
    0xFF1F,
}

# These pairs are drawn as 180-degree counterparts around the CJK em-square
# center (x=500, y=380). Checking the complete family catches an asymmetric
# outline or stale metric even when the affected character is not on the site.
ROTATED_PAIRS = (
    (0x3008, 0x3009),
    (0x300A, 0x300B),
    (0x300C, 0x300D),
    (0x300E, 0x300F),
    (0x3010, 0x3011),
    (0x3014, 0x3015),
    (0x3016, 0x3017),
    (0x3018, 0x3019),
    (0x301A, 0x301B),
    (0xFE17, 0xFE18),
    (0xFE35, 0xFE36),
    (0xFE37, 0xFE38),
    (0xFE39, 0xFE3A),
    (0xFE3B, 0xFE3C),
    (0xFE3D, 0xFE3E),
    (0xFE3F, 0xFE40),
    (0xFE41, 0xFE42),
    (0xFE43, 0xFE44),
    (0xFE47, 0xFE48),
    (0xFF08, 0xFF09),
    (0xFF3B, 0xFF3D),
    (0xFF5B, 0xFF5D),
    (0xFF5F, 0xFF60),
)

# These are the punctuation families Zhongdou deliberately moves to the middle
# of the full-width cell. Other brackets retain their upstream conventions but
# are still covered by bounds, metric, shaping, and pair-symmetry checks.
CENTERED_HORIZONTAL = (0x300C, 0x300D, 0x300E, 0x300F, 0x3014, 0x3015)
CENTERED_VERTICAL = (0xFE41, 0xFE42, 0xFE43, 0xFE44)
CENTERED_MARK_GLYPHS = (
    "uni3001.uv002",
    "uni3002.uv002",
    "uniFF01.uv002",
    "uniFF0C.uv002",
    "uniFF0E.uv002",
    "uniFF1A.uv002",
    "uniFF1B.uv002",
    "uniFF1F.uv002",
)


def fail(message: str) -> None:
    raise ValueError(message)


def glyph_bounds(font: TTFont, glyph_name: str) -> tuple[int, int, int, int]:
    glyph_set = font.getGlyphSet()
    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    if pen.bounds is None:
        fail(f"{glyph_name} has no ink bounds")
    return tuple(round(value) for value in pen.bounds)


def punctuation_codepoints(font: TTFont) -> tuple[int, ...]:
    return tuple(
        codepoint
        for codepoint in sorted(font.getBestCmap())
        if unicodedata.category(chr(codepoint)).startswith("P")
        or codepoint in EXTRA_PUNCTUATION
    )


def close(actual: float, expected: float, tolerance: float = 2) -> bool:
    return abs(actual - expected) <= tolerance


def validate_geometry(font_path: Path) -> tuple[int, ...]:
    variable_font = TTFont(font_path, recalcTimestamp=False)
    codepoints = punctuation_codepoints(variable_font)
    if len(codepoints) != EXPECTED_PUNCTUATION_COUNT:
        fail(
            f"found {len(codepoints)} encoded punctuation characters; "
            f"expected {EXPECTED_PUNCTUATION_COUNT}"
        )
    missing = REQUIRED_CODEPOINTS - set(codepoints)
    if missing:
        fail("missing required punctuation: " + ", ".join(f"U+{cp:04X}" for cp in sorted(missing)))

    for weight in WEIGHTS:
        font = instantiateVariableFont(
            variable_font,
            {"wght": weight},
            inplace=False,
        )
        cmap = font.getBestCmap()

        for codepoint in codepoints:
            glyph_name = cmap[codepoint]
            x_min, _y_min, x_max, _y_max = glyph_bounds(font, glyph_name)
            advance, left_side_bearing = font["hmtx"][glyph_name]
            vertical_advance, _top_side_bearing = font["vmtx"][glyph_name]
            if advance <= 0 or vertical_advance <= 0:
                fail(f"U+{codepoint:04X} has non-positive advance at wght={weight}")
            if not close(left_side_bearing, x_min, 1):
                fail(
                    f"U+{codepoint:04X} has stale horizontal metrics at "
                    f"wght={weight}: lsb={left_side_bearing}, xMin={x_min}"
                )
            # A one-unit overshoot is intentional in a few full-width outlines.
            if x_min < -1 or x_max > advance + 1:
                fail(
                    f"U+{codepoint:04X} escapes its advance at wght={weight}: "
                    f"bounds=({x_min}, {x_max}), advance={advance}"
                )

        for left_codepoint, right_codepoint in ROTATED_PAIRS:
            left_bounds = glyph_bounds(font, cmap[left_codepoint])
            right_bounds = glyph_bounds(font, cmap[right_codepoint])
            mirrored = (
                left_bounds[0] + right_bounds[2],
                left_bounds[2] + right_bounds[0],
                left_bounds[1] + right_bounds[3],
                left_bounds[3] + right_bounds[1],
            )
            if not all(
                close(actual, expected)
                for actual, expected in zip(mirrored, (1000, 1000, 760, 760), strict=True)
            ):
                fail(
                    f"U+{left_codepoint:04X}/U+{right_codepoint:04X} are not "
                    f"mirrored at wght={weight}: {left_bounds}, {right_bounds}"
                )

        for codepoint in CENTERED_HORIZONTAL + CENTERED_VERTICAL:
            bounds = glyph_bounds(font, cmap[codepoint])
            center_x = (bounds[0] + bounds[2]) / 2
            if not close(center_x, 500, 1):
                fail(
                    f"U+{codepoint:04X} is not centered at wght={weight}: "
                    f"x center={center_x}"
                )

        for glyph_name in CENTERED_MARK_GLYPHS:
            bounds = glyph_bounds(font, glyph_name)
            center_x = (bounds[0] + bounds[2]) / 2
            if not close(center_x, 500, 1):
                fail(
                    f"{glyph_name} is not centered at wght={weight}: "
                    f"x center={center_x}"
                )

    return codepoints


def shape(
    hb_shape: str,
    font_path: Path,
    text: str,
    weight: int,
    direction: str,
    features: str,
) -> list[dict[str, int | str]]:
    result = subprocess.run(
        [
            hb_shape,
            f"--language=zh-cn",
            f"--direction={direction}",
            f"--features={features}",
            f"--variations=wght={weight}",
            "--output-format=json",
            "--",
            str(font_path),
            text,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def validate_shaping(font_path: Path, codepoints: tuple[int, ...]) -> None:
    hb_shape = shutil.which("hb-shape")
    if hb_shape is None:
        fail("hb-shape is required; enter the project with `nix develop`")

    text = "".join(chr(codepoint) for codepoint in codepoints)
    for weight in WEIGHTS:
        horizontal = shape(hb_shape, font_path, text, weight, "ltr", "locl,-vert")
        vertical = shape(hb_shape, font_path, text, weight, "ttb", "locl,vert")
        for direction, records in (("horizontal", horizontal), ("vertical", vertical)):
            if len(records) != len(codepoints):
                fail(
                    f"{direction} shaping produced {len(records)} glyphs for "
                    f"{len(codepoints)} punctuation characters at wght={weight}"
                )
            if any(record["g"] == ".notdef" for record in records):
                fail(f"{direction} shaping produced .notdef at wght={weight}")
        if any(record["ax"] <= 0 or record["ay"] != 0 for record in horizontal):
            fail(f"invalid horizontal advances at wght={weight}")
        if any(record["ax"] != 0 or record["ay"] >= 0 for record in vertical):
            fail(f"invalid vertical advances at wght={weight}")

    focus = "〔「『』」〕"
    expected_horizontal = [
        "uni3014",
        "uni300C",
        "uni300E",
        "uni300F",
        "uni300D",
        "uni3015",
    ]
    expected_vertical = [
        "uniFE39",
        "uniFE41",
        "uniFE43",
        "uniFE44",
        "uniFE42",
        "uniFE3A",
    ]
    for weight in WEIGHTS:
        horizontal = shape(hb_shape, font_path, focus, weight, "ltr", "locl,-vert")
        vertical = shape(hb_shape, font_path, focus, weight, "ttb", "locl,vert")
        if [record["g"] for record in horizontal] != expected_horizontal:
            fail(f"unexpected horizontal focused shaping at wght={weight}")
        if [record["g"] for record in vertical] != expected_vertical:
            fail(f"unexpected vertical focused shaping at wght={weight}")


def render_specimens(font_path: Path, output_dir: Path) -> None:
    hb_view = shutil.which("hb-view")
    if hb_view is None:
        fail("hb-view is required; enter the project with `nix develop`")
    output_dir.mkdir(parents=True, exist_ok=True)
    text = "〔「『，。？！⋯・⸺』」〕"
    for weight in WEIGHTS:
        for direction, features in (("ltr", "locl,-vert"), ("ttb", "locl,vert")):
            destination = output_dir / f"punctuation-{direction}-{weight}.png"
            subprocess.run(
                [
                    hb_view,
                    str(font_path),
                    text,
                    f"--output-file={destination}",
                    "--output-format=png",
                    "--font-size=64",
                    "--margin=24",
                    "--language=zh-cn",
                    f"--direction={direction}",
                    f"--features={features}",
                    f"--variations=wght={weight}",
                ],
                check=True,
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=Path)
    parser.add_argument("--render-dir", type=Path)
    arguments = parser.parse_args()

    font_path = arguments.font.resolve()
    codepoints = validate_geometry(font_path)
    validate_shaping(font_path, codepoints)
    if arguments.render_dir is not None:
        render_specimens(font_path, arguments.render_dir.resolve())
    print(
        f"Validated {len(codepoints)} punctuation characters at weights "
        f"{', '.join(str(weight) for weight in WEIGHTS)} in horizontal and vertical layout."
    )


if __name__ == "__main__":
    main()
