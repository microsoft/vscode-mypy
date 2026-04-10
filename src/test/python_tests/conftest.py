# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Shared test fixtures for lsp_server unit tests.

Provides mock LSP dependencies so that ``import lsp_server`` succeeds
without the full VS Code extension environment, and exposes reusable
fixtures for patching the LSP_SERVER singleton.
"""

import pathlib
import sys
import types
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Module-level mock injection
# ---------------------------------------------------------------------------
_INJECTED_MODULES = []
_INJECTED_PATH = None


def setup_lsp_mocks():
    """Inject mock LSP dependencies into ``sys.modules`` and ``sys.path``.

    Tracks what is injected so the ``_lsp_mock_teardown`` fixture can undo it.
    """
    global _INJECTED_PATH

    class _MockLS:
        def __init__(self, *args, **kwargs):
            pass

        def feature(self, *args, **kwargs):
            return lambda f: f

        def command(self, *args, **kwargs):
            return lambda f: f

        # Pygls 1 API (kept for backward-compat with older test files)
        def show_message_log(self, *args, **kwargs):
            pass

        def show_message(self, *args, **kwargs):
            pass

        # Pygls 2 API
        def window_log_message(self, *args, **kwargs):
            pass

        def window_show_message(self, *args, **kwargs):
            pass

    mock_lsp_server_mod = types.ModuleType("pygls.lsp.server")
    mock_lsp_server_mod.LanguageServer = _MockLS

    _Doc = type("Document", (), {"path": None})
    mock_workspace = types.ModuleType("pygls.workspace")
    mock_workspace.Document = _Doc
    mock_workspace.TextDocument = _Doc

    mock_uris = types.ModuleType("pygls.uris")

    def _from_fs_path(path):
        return pathlib.Path(path).as_uri()

    def _to_fs_path(uri):
        if uri.startswith("file:///"):
            path = uri[len("file:///") :]
            if len(path) >= 2 and path[1] == ":":
                return path
            return "/" + path
        return uri

    mock_uris.from_fs_path = _from_fs_path
    mock_uris.to_fs_path = _to_fs_path

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

    class _FlexClass:
        """Accepts arbitrary positional/keyword args (stores kwargs for inspection)."""

        def __init__(self, *args, **kwargs):
            self._kwargs = kwargs

    for _name in [
        "CodeDescription",
        "Diagnostic",
        "DiagnosticSeverity",
        "DidCloseTextDocumentParams",
        "DidOpenTextDocumentParams",
        "DidSaveTextDocumentParams",
        "DocumentFormattingParams",
        "InitializeParams",
        "LogMessageParams",
        "Position",
        "PublishDiagnosticsParams",
        "Range",
        "ShowMessageParams",
        "TextEdit",
    ]:
        setattr(mock_lsp, _name, _FlexClass)
    mock_lsp.MessageType = types.SimpleNamespace(
        Log=4, Error=1, Warning=2, Info=3, Debug=5
    )

    for _mod_name, _mod in [
        ("pygls", types.ModuleType("pygls")),
        ("pygls.lsp", types.ModuleType("pygls.lsp")),
        ("pygls.lsp.server", mock_lsp_server_mod),
        ("pygls.workspace", mock_workspace),
        ("pygls.uris", mock_uris),
        ("lsprotocol", types.ModuleType("lsprotocol")),
        ("lsprotocol.types", mock_lsp),
    ]:
        try:
            __import__(_mod_name)
        except ImportError:
            sys.modules[_mod_name] = _mod
            _INJECTED_MODULES.append(_mod_name)

    # lsp_utils lives in bundled/tool and only uses stdlib —
    # let the real module be imported so tests are not broken by a partial mock.

    tool_dir = str(pathlib.Path(__file__).parents[3] / "bundled" / "tool")
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)
        _INJECTED_PATH = tool_dir


# Run at import time so test modules can ``import lsp_server`` at the top level.
setup_lsp_mocks()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _lsp_mock_teardown():
    """Remove injected mock modules and sys.path entries after the session."""
    yield
    for mod_name in _INJECTED_MODULES:
        sys.modules.pop(mod_name, None)
    _INJECTED_MODULES.clear()
    if _INJECTED_PATH and _INJECTED_PATH in sys.path:
        sys.path.remove(_INJECTED_PATH)


@pytest.fixture()
def patched_lsp_server():
    """Patch ``LSP_SERVER.window_log_message`` and ``window_show_message``
    with ``MagicMock`` instances that are automatically restored after the test.
    """
    import lsp_server

    with patch.object(
        lsp_server.LSP_SERVER, "window_log_message"
    ) as log_mock, patch.object(
        lsp_server.LSP_SERVER, "window_show_message"
    ) as show_mock:
        yield log_mock, show_mock
