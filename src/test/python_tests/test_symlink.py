# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for symlink path resolution in diagnostics matching.
"""

import os
import pathlib
import sys
import tempfile
from threading import Event

import pytest
from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import session, utils

# Add the bundled tool directory to sys.path for importing lsp_utils
BUNDLED_TOOL_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent / "bundled" / "tool"
)
sys.path.insert(0, str(BUNDLED_TOOL_DIR))

import lsp_utils  # noqa: E402

TIMEOUT = 30  # 30 seconds


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


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="os.symlink not available on this platform",
)
def test_symlink_file_diagnostics():
    """Test that type errors in a file accessed via symlink are caught."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create real directory structure
        real_dir = pathlib.Path(tmpdir) / "real_dir"
        real_dir.mkdir()

        # Create a test file with a type error
        test_file = real_dir / "type_error.py"
        test_file.write_text('a: int = 3\na = "hello"\n', encoding="utf-8")

        # Create a symlink to the real directory
        symlink_dir = pathlib.Path(tmpdir) / "symlink_dir"
        try:
            symlink_dir.symlink_to(real_dir)
        except OSError:
            pytest.skip("Unable to create symlink (may require elevated privileges)")

        # Path through symlink (what VSCode would send)
        symlink_file_path = symlink_dir / "type_error.py"
        symlink_file_uri = utils.as_uri(str(symlink_file_path))

        contents = symlink_file_path.read_text(encoding="utf-8")

        actual = {}
        with session.LspSession(cwd=str(symlink_dir)) as ls_session:
            ls_session.initialize()

            done = Event()

            def _handler(params):
                nonlocal actual
                actual = params
                done.set()

            ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": symlink_file_uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            # Wait for diagnostics
            assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

        # Verify diagnostics were received
        assert_that(len(actual.get("diagnostics", [])), greater_than(0))

        # Verify at least one diagnostic mentions the type error (incompatible types)
        messages = [d.get("message", "") for d in actual.get("diagnostics", [])]
        has_type_error = any("Incompatible types" in msg for msg in messages)
        assert_that(has_type_error, is_(True))
