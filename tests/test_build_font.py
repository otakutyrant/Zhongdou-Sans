# pyright: basic, reportAttributeAccessIssue=false
"""Regression coverage for the final Zhongdou font surface."""

from pathlib import Path

from fontTools.ttLib import TTFont

from tools.build_font import CORE_LAYOUT_FEATURES, REMOVED_CODEPOINTS


def test_built_font_keeps_only_the_intended_surface(built_font_path: Path) -> None:
    """Verify names, characters, metrics, and OpenType features together."""
    font = TTFont(built_font_path)
    encoded = {
        codepoint for table in font["cmap"].tables if table.isUnicode() for codepoint in table.cmap
    }
    features = {record.FeatureTag for record in font["GSUB"].table.FeatureList.FeatureRecord}
    families = {record.toUnicode() for record in font["name"].names if record.nameID == 16}

    assert 0x22EF in encoded
    assert encoded.isdisjoint(REMOVED_CODEPOINTS)
    assert features == set(CORE_LAYOUT_FEATURES)
    assert families == {"Zhongdou Sans"}
    assert font["OS/2"].sTypoAscender == 965
    assert font["OS/2"].sTypoDescender == -285
    assert font["hhea"].lineGap == 70
