#!/usr/bin/env python3
"""Build the Zhongdou Sans variable font from the upstream binary.

The upstream repository ships Glyphs source but no automated compiler. This
small, deterministic post-processing step keeps the derivative reproducible on
Linux while making the same feature choices recorded in the Glyphs source.
"""

import argparse
from copy import deepcopy
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


def disable_dlig(font: TTFont) -> None:
    """Keep the feature registered for compatibility, but make it a no-op."""
    disabled = 0
    for record in font["GSUB"].table.FeatureList.FeatureRecord:
        if record.FeatureTag == "dlig":
            record.Feature.LookupListIndex = []
            record.Feature.LookupCount = 0
            disabled += 1
    if disabled == 0:
        raise ValueError("the input font has no dlig feature")


def use_zh_tw_for_zh_cn(font: TTFont) -> None:
    """Give every ZHS language system the corresponding ZHT feature set."""
    updated = 0
    for script_record in font["GSUB"].table.ScriptList.ScriptRecord:
        language_records = {
            record.LangSysTag.strip(): record
            for record in script_record.Script.LangSysRecord or []
        }
        if "ZHS" not in language_records or "ZHT" not in language_records:
            continue
        language_records["ZHS"].LangSys = deepcopy(language_records["ZHT"].LangSys)
        updated += 1
    if updated == 0:
        raise ValueError("the input font has no matching ZHS and ZHT language systems")


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
    disable_dlig(font)
    use_zh_tw_for_zh_cn(font)
    rename_family(font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)


if __name__ == "__main__":
    main()
