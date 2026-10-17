#!/usr/bin/env python3
"""Build the Zhongdou Sans variable font from the upstream binary.

The upstream repository ships Glyphs source but no automated compiler. This
small, deterministic post-processing step keeps the derivative reproducible on
Linux while making the same feature choices recorded in the Glyphs source.
"""

import argparse
from copy import deepcopy
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.iup import iup_delta


FAMILY_REPLACEMENTS = {
    "ZhudouSans": "ZhongdouSans",
    "Zhudou Sans": "Zhongdou Sans",
    "煮豆黑体": "Zhongdou Sans",
    "煮豆黑體": "Zhongdou Sans",
}

# Do not rename names inside legal notices. These records are populated from
# LICENSE separately, retaining upstream notices alongside our own declaration.
LEGAL_NAME_IDS = {0, 13, 14}

REMOVED_CODEPOINTS = (
    set(range(0xFF10, 0xFF1A))
    | set(range(0xFF21, 0xFF3B))
    | set(range(0xFF41, 0xFF5B))
    | {0x229C}
    | set(range(0x1F10D, 0x1F110))
    | set(range(0x1F16D, 0x1F170))
    | set(range(0x1F260, 0x1F266))
)

# Zhongdou is a focused zh-CN punctuation fallback. Keep only localization and
# vertical substitution; inherited alternates, ligatures, width controls, and
# spacing features make its behavior harder to predict without serving that
# purpose.
CORE_LAYOUT_FEATURES = ("locl", "vert")


def use_half_width_quotes_by_default(font: TTFont) -> None:
    """Encode curly quotes as their half-width glyphs without altering features."""
    quote_glyphs = {
        0x2018: "quoteleft.half",
        0x2019: "quoteright.half",
        0x201C: "quotedblleft.half",
        0x201D: "quotedblright.half",
    }
    updated_codepoints = set()
    for table in font["cmap"].tables:
        if not table.isUnicode():
            continue
        for codepoint, glyph_name in quote_glyphs.items():
            if codepoint in table.cmap:
                table.cmap[codepoint] = glyph_name
                updated_codepoints.add(codepoint)

    missing = set(quote_glyphs) - updated_codepoints
    if missing:
        formatted = ", ".join(f"U+{codepoint:04X}" for codepoint in sorted(missing))
        raise ValueError(f"the input font is missing curly quotes in cmap: {formatted}")


def add_midline_ellipsis(font: TTFont) -> None:
    """Map U+22EF to the existing full-width, vertically centered ellipsis."""
    updated = 0
    for table in font["cmap"].tables:
        if not table.isUnicode() or 0x2026 not in table.cmap:
            continue
        if table.cmap[0x2026] != "ellipsis":
            raise ValueError("U+2026 does not map to the expected ellipsis glyph")
        table.cmap[0x22EF] = "ellipsis"
        updated += 1

    if updated == 0:
        raise ValueError("the input font has no Unicode cmap containing U+2026")


def subset_to_supported_characters(font: TTFont) -> None:
    """Remove unrelated characters, alternates, and layout features."""
    encoded = {
        codepoint
        for table in font["cmap"].tables
        if table.isUnicode()
        for codepoint in table.cmap
    }
    variation_selectors = {
        selector
        for table in font["cmap"].tables
        if table.format == 14
        for selector in table.uvsDict
    }
    missing = REMOVED_CODEPOINTS - encoded
    if missing:
        formatted = ", ".join(f"U+{codepoint:04X}" for codepoint in sorted(missing))
        raise ValueError(f"the input font is missing characters to remove: {formatted}")

    options = subset.Options()
    options.glyph_names = True
    options.layout_features = list(CORE_LAYOUT_FEATURES)
    options.layout_scripts = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.name_legacy = True
    options.notdef_outline = True
    # Upstream places full-width A and B at GIDs 2 and 3; retaining the first
    # four "recommended" GIDs would therefore leave those deleted outlines.
    options.recommended_glyphs = False
    options.symbol_cmap = True
    options.legacy_cmap = True

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(
        unicodes=(encoded - REMOVED_CODEPOINTS) | variation_selectors
    )
    subsetter.subset(font)

    # fontTools can leave a syntactically valid but featureless GPOS table
    # behind after pruning. It communicates no behavior and needlessly suggests
    # that the font performs positioning, so remove it altogether.
    if "GPOS" in font and not font["GPOS"].table.FeatureList.FeatureRecord:
        del font["GPOS"]

    retained = {
        record.FeatureTag
        for record in font["GSUB"].table.FeatureList.FeatureRecord
    }
    if retained != set(CORE_LAYOUT_FEATURES):
        raise ValueError(
            f"unexpected retained layout features: {sorted(retained)}; "
            f"expected {sorted(CORE_LAYOUT_FEATURES)}"
        )


def ensure_zh_cn_language_system(font: TTFont) -> None:
    """Keep an explicit ZHS record even when it matches the default system."""
    matched = 0
    for script_record in font["GSUB"].table.ScriptList.ScriptRecord:
        script = script_record.Script
        languages = {
            record.LangSysTag.strip(): record for record in script.LangSysRecord or []
        }
        if script.DefaultLangSys is None:
            continue
        if "ZHS" not in languages:
            record = otTables.LangSysRecord()
            record.LangSysTag = "ZHS "
            record.LangSys = deepcopy(script.DefaultLangSys)
            script.LangSysRecord.append(record)
            script.LangSysRecord.sort(key=lambda item: item.LangSysTag)
            script.LangSysCount = len(script.LangSysRecord)
        matched += 1

    if matched == 0:
        raise ValueError("the subset font has no scripts supporting ZHS")


def harmonize_horizontal_metrics(font: TTFont) -> None:
    """Match Sarasa's line metrics so fallback runs share one baseline."""
    os2 = font["OS/2"]
    os2.sTypoAscender = 965
    os2.sTypoDescender = -285
    os2.sTypoLineGap = 0

    hhea = font["hhea"]
    hhea.ascent = 965
    hhea.descent = -215
    hhea.lineGap = 70


def use_zh_tw_locl_for_zh_cn(font: TTFont) -> None:
    """Use ZHT's centered locl lookup for ZHS without changing other features."""
    feature_records = font["GSUB"].table.FeatureList.FeatureRecord
    updated = 0
    for script_record in font["GSUB"].table.ScriptList.ScriptRecord:
        language_records = {
            record.LangSysTag.strip(): record
            for record in script_record.Script.LangSysRecord or []
        }
        if "ZHS" not in language_records or "ZHT" not in language_records:
            continue

        zhs = language_records["ZHS"].LangSys
        zht = language_records["ZHT"].LangSys
        zht_locl = [
            index
            for index in zht.FeatureIndex
            if feature_records[index].FeatureTag == "locl"
        ]
        if len(zht_locl) != 1:
            raise ValueError(
                f"{script_record.ScriptTag} ZHT has {len(zht_locl)} locl features"
            )

        zhs.FeatureIndex = sorted(
            index
            for index in zhs.FeatureIndex
            if feature_records[index].FeatureTag != "locl"
        )
        zhs.FeatureIndex.append(zht_locl[0])
        zhs.FeatureIndex.sort()
        zhs.FeatureCount = len(zhs.FeatureIndex)
        updated += 1
    if updated == 0:
        raise ValueError("the input font has no matching ZHS and ZHT language systems")


def center_zh_cn_vertical_punctuation(font: TTFont) -> None:
    """Center ZHS and default punctuation before generic vertical substitution."""
    substitutions = {
        "uni3001": "uni3001.uv002",
        "uni3002": "uni3002.uv002",
        "uniFF01": "uniFF01.uv002",
        "uniFF0C": "uniFF0C.uv002",
        "uniFF0E": "uniFF0E.uv002",
        "uniFF1A": "uniFF1A.uv002",
        "uniFF1B": "uniFF1B.uv002",
        "uniFF1F": "uniFF1F.uv002",
    }
    glyphs = set(font.getGlyphOrder())
    missing = (set(substitutions) | set(substitutions.values())) - glyphs
    if missing:
        raise ValueError(f"missing vertical punctuation glyphs: {sorted(missing)}")

    feature_records = font["GSUB"].table.FeatureList.FeatureRecord
    lookup_list = font["GSUB"].table.LookupList.Lookup
    localized_lookups = []
    for lookup_index, lookup in enumerate(lookup_list):
        if lookup.LookupType != 1 or len(lookup.SubTable) != 1:
            continue
        mapping = lookup.SubTable[0].mapping
        if mapping.get("quoteleft") == "uniFE41":
            localized_lookups.append((lookup_index, mapping))
    if len(localized_lookups) != 1:
        raise ValueError(
            f"the input font has {len(localized_lookups)} localized Chinese "
            "vertical lookups"
        )

    localized_lookup_index, mapping = localized_lookups[0]
    conflicts = {
        source: mapping[source]
        for source in substitutions.keys() & mapping.keys()
        if mapping[source] != substitutions[source]
    }
    if conflicts:
        raise ValueError(f"conflicting vertical punctuation substitutions: {conflicts}")
    mapping.update(substitutions)

    matched_scripts = 0

    for script_record in font["GSUB"].table.ScriptList.ScriptRecord:
        language_records = {
            record.LangSysTag.strip(): record
            for record in script_record.Script.LangSysRecord or []
        }
        if "ZHS" not in language_records:
            continue

        zhs = language_records["ZHS"].LangSys
        vert_features = [
            feature_records[index].Feature
            for index in zhs.FeatureIndex
            if feature_records[index].FeatureTag == "vert"
        ]
        if len(vert_features) != 1:
            raise ValueError(
                f"{script_record.ScriptTag} ZHS has {len(vert_features)} vert features"
            )

        vert_feature = vert_features[0]
        if localized_lookup_index not in vert_feature.LookupListIndex:
            vert_feature.LookupListIndex.insert(0, localized_lookup_index)
            vert_feature.LookupCount = len(vert_feature.LookupListIndex)
        matched_scripts += 1

    if matched_scripts == 0:
        raise ValueError("the input font has no ZHS vertical features")


def center_default_language_punctuation(font: TTFont) -> None:
    """Use centered localization when apps omit a supported CJK language."""
    table = font["GSUB"].table
    centered_index = next(
        index
        for script in table.ScriptList.ScriptRecord
        for language in script.Script.LangSysRecord
        if language.LangSysTag.strip() == "ZHT"
        for index in language.LangSys.FeatureIndex
        if table.FeatureList.FeatureRecord[index].FeatureTag == "locl"
    )
    for script in table.ScriptList.ScriptRecord:
        default = script.Script.DefaultLangSys
        if default is None:
            continue
        default.FeatureIndex = sorted(
            {index for index in default.FeatureIndex
             if table.FeatureList.FeatureRecord[index].FeatureTag != "locl"}
            | {centered_index}
        )
        default.FeatureCount = len(default.FeatureIndex)


def translate_glyph(font: TTFont, glyph_name: str, dx: int, dy: int) -> None:
    """Translate a TrueType glyph without changing its advance metrics."""
    glyph = font["glyf"][glyph_name]
    if glyph.isComposite():
        for component in glyph.components:
            component.x += dx
            component.y += dy
    else:
        glyph.coordinates.translate((dx, dy))
    glyph.recalcBounds(font["glyf"])


def translate_glyphs_once(
    font: TTFont,
    glyph_names: tuple[str, ...],
    dx: int,
    dy: int,
    marker_name: str,
    before_bounds: tuple[int, int, int, int],
    after_bounds: tuple[int, int, int, int],
) -> None:
    """Apply a checked, idempotent translation to a related glyph set."""
    marker = font["glyf"][marker_name]
    marker.recalcBounds(font["glyf"])
    bounds = (marker.xMin, marker.yMin, marker.xMax, marker.yMax)
    if bounds == after_bounds:
        return
    if bounds != before_bounds:
        raise ValueError(
            f"unexpected {marker_name} bounds: {bounds}; expected {before_bounds}"
        )
    for glyph_name in glyph_names:
        translate_glyph(font, glyph_name, dx, dy)


def translate_variable_glyph_once(
    font: TTFont,
    glyph_name: str,
    dx: int,
    variation_dx: tuple[int, ...],
    before_bounds: tuple[int, int, int, int],
    after_bounds: tuple[int, int, int, int],
) -> None:
    """Center a variable glyph at every master while retaining its metrics."""
    glyph = font["glyf"][glyph_name]
    glyph.recalcBounds(font["glyf"])
    bounds = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
    if bounds == after_bounds:
        return
    if bounds != before_bounds:
        raise ValueError(
            f"unexpected {glyph_name} bounds: {bounds}; expected {before_bounds}"
        )

    variations = font["gvar"].variations[glyph_name]
    if len(variations) != len(variation_dx):
        raise ValueError(
            f"unexpected {glyph_name} variation count: {len(variations)}; "
            f"expected {len(variation_dx)}"
        )

    coordinates, controls = font["glyf"]._getCoordinatesAndControls(
        glyph_name,
        font["hmtx"].metrics,
        font["vmtx"].metrics,
    )
    outline_length = len(coordinates) - 4
    for variation, tuple_dx in zip(variations, variation_dx, strict=True):
        deltas = iup_delta(variation.coordinates, coordinates, controls.endPts)
        variation.coordinates = [
            (x + tuple_dx, y) if index < outline_length else (x, y)
            for index, (x, y) in enumerate(deltas)
        ]

    translate_glyph(font, glyph_name, dx, 0)


def translate_variable_composite_once(
    font: TTFont,
    glyph_name: str,
    dx: int,
    variation_dx: tuple[int, ...],
    variation_model_glyph: str,
    before_bounds: tuple[int, int, int, int],
    after_bounds: tuple[int, int, int, int],
) -> None:
    """Center a composite whose master offsets have no existing gvar tuples."""
    glyph = font["glyf"][glyph_name]
    glyph.recalcBounds(font["glyf"])
    bounds = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
    if bounds == after_bounds:
        return
    if bounds != before_bounds:
        raise ValueError(
            f"unexpected {glyph_name} bounds: {bounds}; expected {before_bounds}"
        )
    if not glyph.isComposite() or font["gvar"].variations[glyph_name]:
        raise ValueError(f"{glyph_name} is not a variation-free composite")

    model_variations = font["gvar"].variations[variation_model_glyph]
    if len(model_variations) != len(variation_dx):
        raise ValueError(
            f"unexpected {variation_model_glyph} variation count: "
            f"{len(model_variations)}; expected {len(variation_dx)}"
        )

    coordinate_count = len(glyph.components) + 4
    font["gvar"].variations[glyph_name] = [
        TupleVariation(
            variation.axes,
            [(tuple_dx, 0)] * len(glyph.components)
            + [(0, 0)] * (coordinate_count - len(glyph.components)),
        )
        for variation, tuple_dx in zip(
            model_variations, variation_dx, strict=True
        )
    ]
    translate_glyph(font, glyph_name, dx, 0)


def sync_dependent_glyph_metrics(font: TTFont, translated: set[str]) -> None:
    """Synchronize side bearings after moving outlines and their composites."""
    affected = set(translated)
    changed = True
    while changed:
        changed = False
        for glyph_name in font.getGlyphOrder():
            glyph = font["glyf"][glyph_name]
            if glyph_name in affected or not glyph.isComposite():
                continue
            if any(component.glyphName in affected for component in glyph.components):
                affected.add(glyph_name)
                changed = True

    vertical_origin = font["OS/2"].sTypoAscender
    for glyph_name in affected:
        glyph = font["glyf"][glyph_name]
        glyph.recalcBounds(font["glyf"])
        horizontal_advance, _ = font["hmtx"][glyph_name]
        vertical_advance, _ = font["vmtx"][glyph_name]
        font["hmtx"][glyph_name] = (horizontal_advance, glyph.xMin)
        font["vmtx"][glyph_name] = (vertical_advance, vertical_origin - glyph.yMax)


def refine_punctuation_glyphs(font: TTFont) -> None:
    """Center punctuation ink in its em square without changing advances."""
    centered_marks = (
        "uni3001.uv002",
        "uni3002.uv002",
        "uniFF01.uv002",
        "uniFF0C.uv002",
        "uniFF0E.uv002",
        "uniFF1A.uv002",
        "uniFF1B.uv002",
        "uniFF1F.uv002",
    )
    translate_glyphs_once(
        font,
        centered_marks,
        0,
        20,
        "uniFF0E.uv002",
        (463, 338, 537, 422),
        (463, 358, 537, 442),
    )
    translate_variable_glyph_once(
        font,
        "uni3014",
        -337,
        (14, 30),
        (721, -91, 954, 851),
        (384, -91, 617, 851),
    )
    translate_variable_glyph_once(
        font,
        "uni300C",
        -312,
        (5, 7),
        (660, 186, 965, 840),
        (348, 186, 653, 840),
    )
    # The inherited vertical corner quotes straddle the column center. Move
    # each rotated composite onto x=500 at every master while preserving its
    # already-centered vertical position and full-width advance.
    translate_variable_composite_once(
        font,
        "uniFE41",
        -133,
        (-8, -21),
        "uni300C",
        (306, 227, 960, 532),
        (173, 227, 827, 532),
    )
    translate_variable_composite_once(
        font,
        "uniFE42",
        133,
        (8, 21),
        "uni300C",
        (40, 228, 694, 533),
        (173, 228, 827, 533),
    )
    sync_dependent_glyph_metrics(font, set(centered_marks) | {"uni300C", "uni3014"})


def rename_family(font: TTFont) -> None:
    """Replace upstream's reserved family name in derivative name records."""
    for record in font["name"].names:
        if record.nameID in LEGAL_NAME_IDS:
            continue
        value = record.toUnicode()
        for old, new in FAMILY_REPLACEMENTS.items():
            value = value.replace(old, new)
        record.string = value.encode(record.getEncoding())


def embed_license(font: TTFont) -> None:
    """Keep distributed font metadata consistent with the complete LICENSE."""
    license_text = (Path(__file__).resolve().parent.parent / "LICENSE").read_text(
        encoding="utf-8"
    )
    notices = license_text.split("\n\n", 1)[0]
    values = {0: notices, 13: license_text, 14: "https://openfontlicense.org/"}
    names = font["name"]
    for name_id, value in values.items():
        for record in list(names.names):
            if record.nameID == name_id:
                names.setName(
                    value, name_id, record.platformID, record.platEncID, record.langID
                )
        names.setName(value, name_id, 3, 1, 0x409)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("fonts/variable/ZhudouSansVF.ttf"),
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("build/ZhongdouSansVF.ttf"),
    )
    args = parser.parse_args()

    font = TTFont(args.input, recalcTimestamp=False)
    use_half_width_quotes_by_default(font)
    add_midline_ellipsis(font)
    harmonize_horizontal_metrics(font)
    use_zh_tw_locl_for_zh_cn(font)
    center_zh_cn_vertical_punctuation(font)
    center_default_language_punctuation(font)
    refine_punctuation_glyphs(font)
    subset_to_supported_characters(font)
    ensure_zh_cn_language_system(font)
    rename_family(font)
    embed_license(font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)


if __name__ == "__main__":
    main()
