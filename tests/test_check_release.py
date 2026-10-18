# pyright: basic
"""Tests for release-tag and built-font metadata agreement."""

from pathlib import Path

import pytest

from tools.check_release import validate_release


def test_release_metadata_matches_current_version(built_font_path: Path) -> None:
    validate_release("v3.001", built_font_path)


@pytest.mark.parametrize("tag", ["3.001", "v3.1", "release-3.001"])
def test_release_tag_requires_canonical_shape(tag: str, built_font_path: Path) -> None:
    with pytest.raises(ValueError, match="release tags must have the form"):
        validate_release(tag, built_font_path)


def test_release_tag_must_match_font_version(built_font_path: Path) -> None:
    with pytest.raises(ValueError, match="fontRevision"):
        validate_release("v3.002", built_font_path)
