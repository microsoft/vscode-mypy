# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_dmypy_args() custom daemonStatusFile support."""

import os
import pathlib
import sys
import types


# ---------------------------------------------------------------------------
# Stub out bundled LSP dependencies so lsp_server can be imported.
# ---------------------------------------------------------------------------
def _setup_mocks():
    class _MockLS:
        def __init__(self, **kwargs):
            pass

        def feature(self, *args, **kwargs):
            return lambda f: f

        def command(self, *args, **kwargs):
            return lambda f: f

        def show_message_log(self, *args, **kwargs):
            pass

        def show_message(self, *args, **kwargs):
            pass

        def window_log_message(self, *args, **kwargs):
            pass

    mock_server = types.ModuleType("pygls.lsp.server")
    mock_server.LanguageServer = _MockLS

    mock_workspace = types.ModuleType("pygls.workspace")
    mock_workspace.TextDocument = type("TextDocument", (), {"path": None})

    mock_pygls = types.ModuleType("pygls")
    mock_pygls_uris = types.ModuleType("pygls.uris")
    mock_pygls_uris.from_fs_path = lambda p: "file://" + p

    mock_lsp = types.ModuleType("lsprotocol.types")
    for _name in [
        "TEXT_DOCUMENT_DID_OPEN",
        "TEXT_DOCUMENT_DID_SAVE",
        "TEXT_DOCUMENT_DID_CLOSE",
        "TEXT_DOCUMENT_FORMATTING",
        "INITIALIZE",
        "EXIT",
        "SHUTDOWN",
    ]:
        setattr(mock_lsp, _name, _name)
    for _name in [
        "Diagnostic",
        "DiagnosticSeverity",
        "DidCloseTextDocumentParams",
        "DidOpenTextDocumentParams",
        "DidSaveTextDocumentParams",
        "DocumentFormattingParams",
        "InitializeParams",
        "LogMessageParams",
        "Position",
        "Range",
        "TextEdit",
    ]:
        setattr(mock_lsp, _name, type(_name, (), {"__init__": lambda self, **kw: None}))
    mock_lsp.MessageType = type(
        "MessageType", (), {"Log": 4, "Error": 1, "Warning": 2, "Info": 3, "Debug": 5}
    )

    mock_lsp_utils = types.ModuleType("lsp_utils")
    mock_lsp_utils.normalize_path = lambda p: str(pathlib.Path(p).resolve())

    for _mod_name, _mod in [
        ("pygls", mock_pygls),
        ("pygls.lsp", types.ModuleType("pygls.lsp")),
        ("pygls.lsp.server", mock_server),
        ("pygls.workspace", mock_workspace),
        ("pygls.uris", mock_pygls_uris),
        ("lsprotocol", types.ModuleType("lsprotocol")),
        ("lsprotocol.types", mock_lsp),
        ("lsp_utils", mock_lsp_utils),
        ("packaging", types.ModuleType("packaging")),
        ("packaging.version", types.ModuleType("packaging.version")),
    ]:
        if _mod_name not in sys.modules:
            sys.modules[_mod_name] = _mod

    import packaging.version as _pv

    _pv.Version = lambda v: v
    _pv.parse = lambda v: v

    tool_dir = str(pathlib.Path(__file__).parents[3] / "bundled" / "tool")
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)


_setup_mocks()

import lsp_server  # noqa: E402


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
    settings = _make_settings("/workspace/project", "/custom/status.json")
    result = lsp_server._get_dmypy_args(settings, "run")
    assert "--status-file" in result
    idx = result.index("--status-file")
    assert result[idx + 1] == "/custom/status.json"
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
    settings = _make_settings("/workspace/sep_test", "/my/status.json")
    result = lsp_server._get_dmypy_args(settings, "run")
    assert result[-2:] == ["run", "--"]
    _clear_dmypy_cache()


def test_dmypy_args_stop_no_separator():
    """Control commands (stop, kill, etc.) do not include the '--' separator."""
    _clear_dmypy_cache()
    settings = _make_settings("/workspace/stop_test", "/my/status.json")
    result = lsp_server._get_dmypy_args(settings, "stop")
    assert result[-1] == "stop"
    assert "--" not in result[result.index("stop") :]
    _clear_dmypy_cache()


def test_dmypy_args_caches_per_workspace():
    """DMYPY_ARGS are cached per workspace; the status file is set once."""
    _clear_dmypy_cache()
    settings = _make_settings("/workspace/cached", "/cached/status.json")
    result1 = lsp_server._get_dmypy_args(settings, "run")
    result2 = lsp_server._get_dmypy_args(settings, "check")
    # Both should use the same status file
    idx1 = result1.index("--status-file")
    idx2 = result2.index("--status-file")
    assert result1[idx1 + 1] == result2[idx2 + 1] == "/cached/status.json"
    _clear_dmypy_cache()
