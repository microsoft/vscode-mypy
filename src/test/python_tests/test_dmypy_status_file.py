# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_dmypy_args() custom daemonStatusFile support."""

import os
import pathlib

import lsp_server


def _make_settings(workspace_path, daemon_status_file=""):
    return {
        "workspaceFS": workspace_path,
        "daemonStatusFile": daemon_status_file,
    }


def _clear_dmypy_cache():
    lsp_server.DMYPY_ARGS.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dmypy_args_uses_custom_status_file():
    """When daemonStatusFile is set, _get_dmypy_args uses it instead of generating one."""
    _clear_dmypy_cache()
    try:
        settings = _make_settings("/workspace/project", "/custom/status.json")
        result = lsp_server._get_dmypy_args(settings, "run")
        assert "--status-file" in result
        idx = result.index("--status-file")
        assert result[idx + 1] == "/custom/status.json"
    finally:
        _clear_dmypy_cache()


def test_dmypy_args_generates_status_file_when_not_set():
    """When daemonStatusFile is empty, _get_dmypy_args generates a unique status file."""
    _clear_dmypy_cache()
    # Ensure DMYPY_STATUS_FILE_ROOT is set for auto-generation
    old_root = lsp_server.DMYPY_STATUS_FILE_ROOT
    lsp_server.DMYPY_STATUS_FILE_ROOT = pathlib.Path(os.environ.get("TEMP", "/tmp"))
    try:
        settings = _make_settings("/workspace/auto", "")
        result = lsp_server._get_dmypy_args(settings, "run")
        assert "--status-file" in result
        idx = result.index("--status-file")
        # Should be a generated path, not empty
        assert result[idx + 1] != ""
        assert "status-" in result[idx + 1]
    finally:
        lsp_server.DMYPY_STATUS_FILE_ROOT = old_root
        _clear_dmypy_cache()


def test_dmypy_args_run_includes_separator():
    """The 'run' command includes a '--' separator after the command."""
    _clear_dmypy_cache()
    try:
        settings = _make_settings("/workspace/sep_test", "/my/status.json")
        result = lsp_server._get_dmypy_args(settings, "run")
        assert result[-2:] == ["run", "--"]
    finally:
        _clear_dmypy_cache()


def test_dmypy_args_stop_no_separator():
    """Control commands (stop, kill, etc.) do not include the '--' separator."""
    _clear_dmypy_cache()
    try:
        settings = _make_settings("/workspace/stop_test", "/my/status.json")
        result = lsp_server._get_dmypy_args(settings, "stop")
        assert result[-1] == "stop"
        assert "--" not in result[result.index("stop") :]
    finally:
        _clear_dmypy_cache()


def test_dmypy_args_caches_per_workspace():
    """DMYPY_ARGS are cached per workspace; the status file is set once."""
    _clear_dmypy_cache()
    try:
        settings = _make_settings("/workspace/cached", "/cached/status.json")
        result1 = lsp_server._get_dmypy_args(settings, "run")
        result2 = lsp_server._get_dmypy_args(settings, "check")
        # Both should use the same status file
        idx1 = result1.index("--status-file")
        idx2 = result2.index("--status-file")
        assert result1[idx1 + 1] == result2[idx2 + 1] == "/cached/status.json"
    finally:
        _clear_dmypy_cache()
