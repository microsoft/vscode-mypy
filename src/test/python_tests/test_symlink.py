# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for symlink path resolution in diagnostics matching.
"""

import os
import pathlib
import sys
import tempfile

import pytest
from hamcrest import assert_that, is_

# Add the bundled tool directory to sys.path for importing lsp_utils
BUNDLED_TOOL_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent / "bundled" / "tool"
)
sys.path.insert(0, str(BUNDLED_TOOL_DIR))

import lsp_utils  # noqa: E402


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="os.symlink not available on this platform",
)
def test_is_same_path_with_symlink():
    """Test that is_same_path correctly identifies paths through symlinks as equal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create real directory structure
        real_dir = pathlib.Path(tmpdir) / "real_dir"
        real_dir.mkdir()

        # Create a test file
        test_file = real_dir / "test_file.py"
        test_file.write_text("# test file", encoding="utf-8")

        # Create a symlink to the real directory
        symlink_dir = pathlib.Path(tmpdir) / "symlink_dir"
        try:
            symlink_dir.symlink_to(real_dir)
        except OSError:
            pytest.skip("Unable to create symlink (may require elevated privileges)")

        # Real path (what mypy would report with --show-absolute-path)
        real_file_path = str(real_dir / "test_file.py")
        # Path through symlink (what VSCode would send)
        symlink_file_path = str(symlink_dir / "test_file.py")

        # Verify the paths are different strings
        assert_that(real_file_path == symlink_file_path, is_(False))

        # But is_same_path should identify them as the same file
        assert_that(
            lsp_utils.is_same_path(real_file_path, symlink_file_path), is_(True)
        )
        assert_that(
            lsp_utils.is_same_path(symlink_file_path, real_file_path), is_(True)
        )


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="os.symlink not available on this platform",
)
def test_is_same_path_different_files():
    """Test that is_same_path correctly identifies different files as not equal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two different files
        file1 = pathlib.Path(tmpdir) / "file1.py"
        file2 = pathlib.Path(tmpdir) / "file2.py"
        file1.write_text("# file 1", encoding="utf-8")
        file2.write_text("# file 2", encoding="utf-8")

        # Different files should not be equal
        assert_that(lsp_utils.is_same_path(str(file1), str(file2)), is_(False))


def test_is_same_path_same_file():
    """Test that is_same_path correctly identifies the same file as equal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = pathlib.Path(tmpdir) / "test.py"
        test_file.write_text("# test", encoding="utf-8")

        # Same path should be equal
        assert_that(lsp_utils.is_same_path(str(test_file), str(test_file)), is_(True))
