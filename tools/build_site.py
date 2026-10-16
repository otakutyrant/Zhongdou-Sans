#!/usr/bin/env python3
"""Build the static GitHub Pages site with content-specific webfont subsets."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont


class VisibleText(HTMLParser):
    """Collect visible HTML text and accessible labels used by the page."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        for name, value in attrs:
            if name in {"aria-label", "content"} and value:
                self.parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0:
            self.parts.append(data)


def page_codepoints(index_path: Path) -> set[int]:
    parser = VisibleText()
    parser.feed(index_path.read_text(encoding="utf-8"))
    return {ord(character) for character in "".join(parser.parts) if not character.isspace()}


def write_subset(font: TTFont, codepoints: set[int], destination: Path) -> None:
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.recalc_timestamp = False

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(destination, reorderTables=False)


def build(project_root: Path, sarasa_ttc: Path) -> Path:
    source_dir = project_root / "site"
    output_dir = project_root / "build" / "site"
    font_dir = output_dir / "fonts"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(source_dir, output_dir)
    font_dir.mkdir()

    codepoints = page_codepoints(source_dir / "index.html")
    source_zhudou = project_root / "fonts" / "variable" / "ZhudouSansVF.ttf"
    built_zhongdou = project_root / "build" / "ZhongdouSansVF.ttf"
    subprocess.run(
        [
            sys.executable,
            str(project_root / "tools" / "build_font.py"),
            str(source_zhudou),
            str(built_zhongdou),
        ],
        check=True,
    )

    zhongdou = TTFont(built_zhongdou, recalcTimestamp=False)
    write_subset(zhongdou, codepoints, font_dir / "ZhongdouSans-subset.woff2")

    # Sarasa-Regular.ttc stores Sarasa Gothic SC at collection index 1.
    sarasa = TTFont(sarasa_ttc, fontNumber=1, recalcTimestamp=False)
    write_subset(sarasa, codepoints, font_dir / "SarasaGothicSC-subset.woff2")

    for path in sorted(font_dir.glob("*.woff2")):
        print(f"{path.relative_to(project_root)}: {path.stat().st_size / 1024:.1f} KiB")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--sarasa-ttc", type=Path, required=True)
    arguments = parser.parse_args()

    output = build(arguments.project_root.resolve(), arguments.sarasa_ttc.resolve())
    print(f"Built {output}")


if __name__ == "__main__":
    main()
