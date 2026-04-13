# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_global_defaults() in lsp_server.

Verifies that global-level settings (e.g. ignorePatterns) propagate into the
defaults returned by _get_global_defaults(), which serves as the fallback for
per-workspace settings.
"""

import lsp_server
import pytest


def _with_global_settings(overrides):
    """Context-manager-like helper that restores GLOBAL_SETTINGS on exit."""

    class _Ctx:
        def __enter__(self):
            self._old = lsp_server.GLOBAL_SETTINGS.copy()
            lsp_server.GLOBAL_SETTINGS.update(overrides)
            return self

        def __exit__(self, *args):
            lsp_server.GLOBAL_SETTINGS.clear()
            lsp_server.GLOBAL_SETTINGS.update(self._old)

    return _Ctx()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides, pop_key, key, expected",
    [
        pytest.param(
            {"ignorePatterns": ["*.pyi", "test_*"]},
            None,
            "ignorePatterns",
            ["*.pyi", "test_*"],
            id="ignorePatterns-set",
        ),
        pytest.param(
            {}, "ignorePatterns", "ignorePatterns", [], id="ignorePatterns-default"
        ),
        pytest.param(
            {"daemonStatusFile": "/custom/status.json"},
            None,
            "daemonStatusFile",
            "/custom/status.json",
            id="daemonStatusFile-set",
        ),
        pytest.param(
            {},
            "daemonStatusFile",
            "daemonStatusFile",
            "",
            id="daemonStatusFile-default",
        ),
    ],
)
def test_global_defaults_setting(overrides, pop_key, key, expected):
    """Each global setting is correctly read or defaults when absent."""
    with _with_global_settings(overrides):
        if pop_key:
            lsp_server.GLOBAL_SETTINGS.pop(pop_key, None)
        defaults = lsp_server._get_global_defaults()
        assert defaults[key] == expected
