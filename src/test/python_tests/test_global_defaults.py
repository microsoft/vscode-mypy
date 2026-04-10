# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_global_defaults() in lsp_server.

Verifies that global-level settings (e.g. ignorePatterns) propagate into the
defaults returned by _get_global_defaults(), which serves as the fallback for
per-workspace settings.
"""

import lsp_server


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


def test_global_defaults_ignorePatterns_from_global_settings():
    """ignorePatterns set in GLOBAL_SETTINGS are returned by _get_global_defaults."""
    with _with_global_settings({"ignorePatterns": ["*.pyi", "test_*"]}):
        defaults = lsp_server._get_global_defaults()
        assert defaults["ignorePatterns"] == ["*.pyi", "test_*"]


def test_global_defaults_ignorePatterns_empty_when_not_set():
    """ignorePatterns defaults to [] when not present in GLOBAL_SETTINGS."""
    with _with_global_settings({}):
        # Ensure ignorePatterns is not in GLOBAL_SETTINGS
        lsp_server.GLOBAL_SETTINGS.pop("ignorePatterns", None)
        defaults = lsp_server._get_global_defaults()
        assert defaults["ignorePatterns"] == []


def test_global_defaults_daemonStatusFile_from_global_settings():
    """daemonStatusFile set in GLOBAL_SETTINGS is returned by _get_global_defaults."""
    with _with_global_settings({"daemonStatusFile": "/custom/status.json"}):
        defaults = lsp_server._get_global_defaults()
        assert defaults["daemonStatusFile"] == "/custom/status.json"


def test_global_defaults_daemonStatusFile_empty_when_not_set():
    """daemonStatusFile defaults to '' when not present in GLOBAL_SETTINGS."""
    with _with_global_settings({}):
        lsp_server.GLOBAL_SETTINGS.pop("daemonStatusFile", None)
        defaults = lsp_server._get_global_defaults()
        assert defaults["daemonStatusFile"] == ""
