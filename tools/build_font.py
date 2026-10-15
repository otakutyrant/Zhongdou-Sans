#!/usr/bin/env python3
"""Build the Zhongdou Sans variable font from the upstream binary.

The upstream repository ships Glyphs source but no automated compiler. This
small, deterministic post-processing step keeps the derivative reproducible on
Linux while making the same feature choices recorded in the Glyphs source.
"""

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.iup import iup_delta


FAMILY_REPLACEMENTS = {
    "ZhudouSans": "ZhongdouSans",
    "Zhudou Sans": "Zhongdou Sans",
    "煮豆黑体": "Zhongdou Sans",
    "煮豆黑體": "Zhongdou Sans",
}

# Preserve copyright and licence records verbatim, including the declaration
# of upstream's reserved font name. All actual derivative-family identifiers
# are renamed below as required by the SIL Open Font License.
LEGAL_NAME_IDS = {0, 13, 14}


def feature_by_tag(font: TTFont, table_tag: str, tag: str):
    for record in font[table_tag].table.FeatureList.FeatureRecord:
        if record.FeatureTag == tag:
            return record.Feature
    raise ValueError(f"the input font has no {tag} feature in {table_tag}")


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


def disable_positioning_features(font: TTFont) -> None:
    """Keep spacing feature tags registered, but make them no-ops."""
    feature_tags = {"halt", "kern", "vhal", "vkrn"}
    disabled = set()
    for record in font["GPOS"].table.FeatureList.FeatureRecord:
        if record.FeatureTag in feature_tags:
            record.Feature.LookupListIndex = []
            record.Feature.LookupCount = 0
            disabled.add(record.FeatureTag)
    if disabled != feature_tags:
        raise ValueError(f"missing positioning features: {sorted(feature_tags - disabled)}")


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
        "uniFF0C.ss02": "uniFF0C.uv002.ss02",
        "uniFF0E": "uniFF0E.uv002",
        "uniFF1A": "uniFF1A.uv002",
        "uniFF1B": "uniFF1B.uv002",
        "uniFF1B.ss02": "uniFF1B.uv002.ss02",
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
        "uniFF0C.uv002.ss02",
        "uniFF0E.uv002",
        "uniFF1A.uv002",
        "uniFF1B.uv002",
        "uniFF1B.uv002.ss02",
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
    disable_positioning_features(font)
    use_zh_tw_locl_for_zh_cn(font)
    center_zh_cn_vertical_punctuation(font)
    center_default_language_punctuation(font)
    refine_punctuation_glyphs(font)
    rename_family(font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)


if __name__ == "__main__":
    main()
