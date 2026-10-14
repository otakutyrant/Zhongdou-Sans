#!/usr/bin/env python3
"""Build the Zhongdou Sans variable font from the upstream binary.

The upstream repository ships Glyphs source but no automated compiler. This
small, deterministic post-processing step keeps the derivative reproducible on
Linux while making the same feature choices recorded in the Glyphs source.
"""

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont


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


def reduce_line_gaps(font: TTFont) -> None:
    """Replace upstream's accidental one-em horizontal line gaps."""
    font["OS/2"].sTypoLineGap = 200
    font["hhea"].lineGap = 200


def disable_positioning_features(font: TTFont) -> None:
    """Keep kern and vkrn registered for compatibility, but make them no-ops."""
    disabled = set()
    for record in font["GPOS"].table.FeatureList.FeatureRecord:
        if record.FeatureTag in {"kern", "vkrn"}:
            record.Feature.LookupListIndex = []
            record.Feature.LookupCount = 0
            disabled.add(record.FeatureTag)
    if disabled != {"kern", "vkrn"}:
        raise ValueError(f"missing positioning features: {sorted({'kern', 'vkrn'} - disabled)}")


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
    reduce_line_gaps(font)
    disable_positioning_features(font)
    use_zh_tw_locl_for_zh_cn(font)
    center_zh_cn_vertical_punctuation(font)
    rename_family(font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)


if __name__ == "__main__":
    main()
