# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_global_defaults() in lsp_server.

Verifies that global-level settings (e.g. ignorePatterns) propagate into the
defaults returned by _get_global_defaults(), which serves as the fallback for
per-workspace settings.
"""

import pathlib
import sys
import types


# ---------------------------------------------------------------------------
# Stub out bundled LSP dependencies so lsp_server can be imported without the
# full VS Code extension environment.
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
