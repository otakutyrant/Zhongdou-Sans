# pyright: basic
"""Tests for static-site text collection and font subsetting."""

from pathlib import Path

from fontTools.ttLib import TTFont

from tools.build_site import page_codepoints, write_subset


def test_page_codepoints_collects_visible_and_accessible_text(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<meta content="说明"><p aria-label="句读">文字。</p>'
        "<style>隐藏样式</style><script>隐藏脚本</script>",
        encoding="utf-8",
    )

    codepoints = page_codepoints(page)

    assert set(map(ord, "说明句读文字。")) <= codepoints
    assert codepoints.isdisjoint(set(map(ord, "隐藏样式脚本")))


def test_write_subset_contains_only_requested_characters(
    built_font_path: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "subset.woff2"
    font = TTFont(built_font_path, recalcTimestamp=False)

    write_subset(font, {0x3002, 0xFF0C}, destination)

    subset = TTFont(destination)
    encoded = {
        codepoint
        for table in subset["cmap"].tables
        if table.isUnicode()
        for codepoint in table.cmap
    }
    assert encoded == {0x3002, 0xFF0C}
