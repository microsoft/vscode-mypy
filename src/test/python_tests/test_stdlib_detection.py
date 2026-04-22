# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Tests for stdlib file detection.

Verifies ``is_stdlib_file`` from ``lsp_utils`` correctly identifies
standard-library and known Python paths vs. arbitrary user files.
"""

import os
import site
import sysconfig
import tempfile

from lsp_utils import is_stdlib_file


def test_stdlib_file_detection():
    """Actual stdlib files are correctly identified."""
    os_file = os.__file__
    assert is_stdlib_file(
        os_file
    ), f"os module file {os_file} should be detected as stdlib"


def test_random_file_not_stdlib():
    """Random user files are NOT identified as stdlib."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = is_stdlib_file(tmp_path)
        assert not result, f"Temporary file {tmp_path} should NOT be detected as stdlib"
    finally:
        os.unlink(tmp_path)


def test_known_sysconfig_paths_detected():
    """Files under sysconfig stdlib/platstdlib paths are detected."""
    stdlib_path = sysconfig.get_path("stdlib")
    if stdlib_path:
        test_file = os.path.join(stdlib_path, "json", "__init__.py")
        assert is_stdlib_file(
            test_file
        ), f"File under stdlib path {test_file} should be detected"


def test_site_packages_in_stdlib_paths():
    """In mypy, _stdlib_paths includes site-packages directories."""
    site_packages = site.getsitepackages()

    for site_pkg_dir in site_packages:
        test_file = os.path.join(site_pkg_dir, "pytest", "__init__.py")
        result = is_stdlib_file(test_file)
        assert result, (
            f"File in site-packages {test_file} should be detected "
            f"(mypy _stdlib_paths includes site-packages)"
        )


def test_nonexistent_path_not_stdlib():
    """A fabricated path outside all known Python directories is not stdlib."""
    if os.name == "nt":
        test_file = "Z:\\nonexistent\\random_dir\\module.py"
    else:
        test_file = "/nonexistent/random_dir/module.py"
    assert not is_stdlib_file(
        test_file
    ), f"Fabricated path {test_file} should NOT be detected as stdlib"
