# pyright: basic
"""Shared fixtures for deterministic font-tool regression tests."""

from pathlib import Path

import pytest

from tools.build_font import build_font

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def built_font_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build one Zhongdou font for all tests that inspect final tables."""
    output = tmp_path_factory.mktemp("font") / "ZhongdouSansVF.ttf"
    build_font(PROJECT_ROOT / "fonts/variable/ZhudouSansVF.ttf", output)
    return output
