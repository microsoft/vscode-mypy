# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Utility functions and classes for use with running tools over LSP.

Thin wrapper: delegates to vscode-common-python-lsp shared package,
providing backward-compatible names used by lsp_server.py.
"""

from __future__ import annotations

import os
import pathlib
import re

from vscode_common_python_lsp import (
    CWD_LOCK,
    SERVER_CWD,
    CustomIO,
    PythonFileKind,
    QuickFixRegistrationError,
    RunResult,
    as_list,
    change_cwd,
    classify_python_file,
    is_current_interpreter,
    is_match,
    is_same_path,
    normalize_path,
    redirect_io,
    run_api,
    run_module,
    run_path as _run_path,
    substitute_attr,
)

# -------------------------------------------------------------------------
# Mypy-specific constants (not part of shared package)
# -------------------------------------------------------------------------
ERROR_CODE_BASE_URL = "https://mypy.readthedocs.io/en/latest/_refs.html#code-"
SEE_HREF_PREFIX = "See https://mypy.readthedocs.io"
SEE_PREFIX_LEN = len("See ")
NOTE_CODE = "note"
LINE_OFFSET = CHAR_OFFSET = 1

# Regex pattern to parse mypy diagnostic output lines.
# Format: filepath:line[:char][:end_line:end_char]: type: message  [code]
# Example: /path/to/file.py:14:16:19:5: error: Value of type variable...  [type-var]
# Key features:
# - (?:\s{2}\[(?P<code>[\w-]+)\])? - Optional error code with double-space separator
# - \s*$ - Tolerates trailing whitespace (spaces, tabs, etc.)
DIAGNOSTIC_RE = re.compile(
    r"^(?P<location>(?P<filepath>..[^:]*):(?P<line>\d+)(?::(?P<char>\d+))?(?::(?P<end_line>\d+):(?P<end_char>\d+))?): (?P<type>\w+): (?P<message>.*?)(?:\s{2}\[(?P<code>[\w-]+)\])?\s*$"
)

__all__ = [
    "SERVER_CWD",
    "CWD_LOCK",
    "as_list",
    "normalize_path",
    "is_same_path",
    "is_current_interpreter",
    "is_user_site_packages_file",
    "is_system_site_packages_file",
    "is_stdlib_file",
    "is_match",
    "RunResult",
    "CustomIO",
    "substitute_attr",
    "redirect_io",
    "change_cwd",
    "run_module",
    "run_path",
    "run_api",
    "QuickFixRegistrationError",
    "ERROR_CODE_BASE_URL",
    "SEE_HREF_PREFIX",
    "SEE_PREFIX_LEN",
    "NOTE_CODE",
    "LINE_OFFSET",
    "CHAR_OFFSET",
    "DIAGNOSTIC_RE",
    "absolute_path",
]


def run_path(argv, cwd, env=None) -> RunResult:
    """Runs as an executable (backward-compatible wrapper).

    Mypy passes a partial env dict (extra vars only) — merge with os.environ
    to preserve the full environment, matching the original behavior.
    """
    new_env = os.environ.copy()
    if env is not None:
        new_env.update(env)
    return _run_path(argv=argv, use_stdin=False, cwd=cwd, env=new_env)


def absolute_path(file_path: str) -> str:
    """Returns absolute path without symlink resolve."""
    return str(pathlib.Path(file_path).absolute())


def is_user_site_packages_file(file_path: str) -> bool:
    """Return True if the file belongs to the user site-packages directory."""
    return classify_python_file(file_path) == PythonFileKind.USER_SITE


def is_system_site_packages_file(file_path: str) -> bool:
    """Return True if the file belongs to system site-packages directories."""
    return classify_python_file(file_path) == PythonFileKind.SYSTEM_SITE


def is_stdlib_file(file_path: str) -> bool:
    """Return True if the file belongs to a non-user Python path."""
    return classify_python_file(file_path) is not None
