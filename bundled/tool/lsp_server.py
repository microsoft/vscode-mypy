# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Implementation of tool support over LSP."""

from __future__ import annotations

import copy
import os
import pathlib
import sys
import tempfile
import threading
import traceback
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


# **********************************************************
# Update sys.path before importing any bundled libraries.
# **********************************************************
def update_sys_path(path_to_add: str, strategy: str) -> None:
    """Add given path to `sys.path`."""
    if path_to_add not in sys.path and os.path.isdir(path_to_add):
        if strategy == "useBundled":
            sys.path.insert(0, path_to_add)
        else:
            sys.path.append(path_to_add)


# Ensure that we can import LSP libraries, and other bundled libraries.
BUNDLE_DIR = pathlib.Path(__file__).parent.parent
BUNDLED_LIBS = os.fspath(BUNDLE_DIR / "libs")
# Always use bundled server files.
update_sys_path(os.fspath(BUNDLE_DIR / "tool"), "useBundled")
update_sys_path(
    BUNDLED_LIBS,
    os.getenv("LS_IMPORT_STRATEGY", "useBundled"),
)
# **********************************************************
# Imports needed for the language server goes below this.
# **********************************************************
import lsp_utils as utils
import lsprotocol.types as lsp
from packaging.version import Version
from packaging.version import parse as parse_version
from pygls import uris
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument
from vscode_common_python_lsp import (
    RunResult,
    ToolServer,
    ToolServerConfig,
    is_match,
    normalize_path,
    update_environ_path,
)

update_environ_path()

MAX_WORKERS = 5
LSP_SERVER = LanguageServer(name="Mypy", version="v0.1.0", max_workers=MAX_WORKERS)

DMYPY_ARGS = {}
DMYPY_STATUS_FILE_ROOT = None

# **********************************************************
# Tool specific code goes below this.
# **********************************************************
MYPY_CONFIG = ToolServerConfig(
    tool_module="mypy",
    tool_display="Mypy",
    tool_args=[
        "--no-color-output",
        "--no-error-summary",
        "--show-absolute-path",
        "--show-column-numbers",
        "--show-error-codes",
        "--no-pretty",
    ],
    min_version="1.0.0",
    default_settings={
        "severity": {
            "error": "Error",
            "note": "Information",
        },
        "ignorePatterns": [],
        "extraPaths": [],
        "reportingScope": "file",
        "preferDaemon": True,
        "daemonStatusFile": "",
    },
)

tool_server = ToolServer(MYPY_CONFIG, server=LSP_SERVER)

WORKSPACE_SETTINGS = tool_server.workspace_settings
GLOBAL_SETTINGS = tool_server.global_settings

TOOL_MODULE = MYPY_CONFIG.tool_module
TOOL_DISPLAY = MYPY_CONFIG.tool_display
TOOL_ARGS = MYPY_CONFIG.tool_args
MIN_VERSION = MYPY_CONFIG.min_version

# **********************************************************
# Linting features start here
# **********************************************************


@dataclass
class MypyInfo:
    version: Version
    is_daemon: bool


# Stores infomation of `mypy` executable in various workspaces.
MYPY_INFO_TABLE: Dict[str, MypyInfo] = {}


def get_mypy_info(settings: Dict[str, Any]) -> Optional[MypyInfo]:
    try:
        code_workspace = settings["workspaceFS"]
        if code_workspace not in MYPY_INFO_TABLE:
            # This is text we get from running `mypy --version`
            # mypy 1.0.0 (compiled: yes) <--- This is the version we want.
            result = _run_unidentified_tool(["--version"], copy.deepcopy(settings))
            log_to_output(
                f"Version info for linter running for {code_workspace}:\r\n{result.stdout}"
            )
            first_line = result.stdout.splitlines(keepends=False)[0]
            is_daemon = first_line.startswith("dmypy")
            version_str = first_line.split(" ")[1]
            version = parse_version(version_str)
            MYPY_INFO_TABLE[code_workspace] = MypyInfo(version, is_daemon)
        return MYPY_INFO_TABLE[code_workspace]
    except:  # noqa: E722
        log_error(
            f"Mypy failed to run. Check that mypy is installed and the "
            f"'mypy-type-checker.interpreter' or 'mypy-type-checker.path' "
            f"settings are correct.\r\n{traceback.format_exc()}"
        )
        return None


def _run_unidentified_tool(
    extra_args: Sequence[str], settings: Dict[str, Any]
) -> RunResult:
    """Runs the tool given by the settings without knowing what it is.

    This is supposed to be called only in `get_mypy_info`.
    """
    cwd = get_cwd(settings, None)

    if settings["path"]:
        argv = settings["path"]
    else:
        argv = settings["interpreter"] or [sys.executable]
        argv += ["-m", "mypy.dmypy" if settings["preferDaemon"] else "mypy"]

    argv += extra_args
    log_to_output(" ".join(argv))
    log_to_output(f"CWD Server: {cwd}")

    result = utils.run_path(argv=argv, cwd=cwd, env=_get_env_vars(settings))
    if result.stderr:
        log_to_output(result.stderr)

    log_to_output(f"\r\n{result.stdout}\r\n")
    return result


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
    """LSP handler for textDocument/didOpen request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    _linting_helper(document)


# Track lint request versions per URI to discard stale results from superseded runs.
# This is a deduplication mechanism (not debounce): each save spawns a lint process,
# but only the latest result is published. Rapid saves produce multiple runs where
# only the last one's output is kept.
_lint_versions: Dict[str, int] = {}
_lint_versions_lock = threading.Lock()


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    """LSP handler for textDocument/didSave request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    _linting_helper(document)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
    """LSP handler for textDocument/didClose request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    settings = _get_settings_by_document(document)
    if settings["reportingScope"] == "file":
        # Publishing empty diagnostics to clear the entries for this file.
        _clear_diagnostics(document)
    # Clean up lint version tracking for closed documents
    with _lint_versions_lock:
        _lint_versions.pop(document.uri, None)


def _is_empty_diagnostics(
    filepath: str, results: Optional[Dict[str, str | None]]
) -> bool:
    if results is None:
        return True
    for reported_path, diagnostics in results.items():
        if utils.is_same_path(filepath, reported_path) and diagnostics:
            return False
    return True


_reported_file_paths = set()


def _clear_diagnostics(document: TextDocument) -> None:
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=[])
    )


# Patterns that indicate mypy misconfiguration or startup errors.
# Only patterns that are unambiguously mypy infrastructure errors, not
# normal type-checking diagnostics for user code.  "No module named",
# "missing imports", and "Cannot find implementation or library stub" are
# excluded because they are routine diagnostic messages (especially in
# daemon mode where diagnostics are emitted on stderr).
_MISCONFIGURATION_PATTERNS = [
    "mypy: error:",
    "Could not find a config file",
    "Error constructing plugin",
    "plugin is not installed",
    "invalid config",
]

# Track last reported misconfiguration to suppress duplicates
_last_misconfiguration_msg: Dict[str, str] = {}


def _check_for_misconfiguration(stderr: str) -> None:
    """Check stderr for common misconfiguration patterns and surface them
    as user-visible error notifications. Only reports each unique message once."""
    for line in stderr.splitlines():
        line_lower = line.lower()
        for pattern in _MISCONFIGURATION_PATTERNS:
            if pattern.lower() in line_lower:
                msg = stderr.strip()
                if msg != _last_misconfiguration_msg.get("msg"):
                    _last_misconfiguration_msg["msg"] = msg
                    log_error(f"Mypy configuration issue detected:\r\n{msg}")
                return


def _linting_helper(document: TextDocument) -> None:
    try:
        extra_args = []

        # deep copy here to prevent accidentally updating global settings.
        settings = copy.deepcopy(_get_settings_by_document(document))

        if str(document.uri).startswith("vscode-notebook-cell"):
            # We don't support running mypy on notebook cells.
            log_warning(f"Skipping notebook cells [Not Supported]: {str(document.uri)}")
            _clear_diagnostics(document)
            return None

        if settings["reportingScope"] == "file" and utils.is_stdlib_file(document.path):
            log_warning(
                f"Skipping standard library file (stdlib excluded): {document.path}"
            )
            _clear_diagnostics(document)
            return None

        if settings["reportingScope"] == "file" and is_match(
            settings["ignorePatterns"], document.path, settings["workspaceFS"]
        ):
            log_warning(
                f"Skipping file due to `mypy-type-checker.ignorePatterns` match: {document.path}"
            )
            _clear_diagnostics(document)
            return None

        mypy_info = get_mypy_info(settings)
        if mypy_info is None:
            _clear_diagnostics(document)
            return None

        # Bump the version for this URI so any concurrent or queued lint for
        # the same document can detect that it has been superseded.
        with _lint_versions_lock:
            lint_version = _lint_versions.get(document.uri, 0) + 1
            _lint_versions[document.uri] = lint_version

        version = mypy_info.version
        if (version.major, version.minor) >= (0, 991) and sys.version_info >= (3, 8):
            extra_args += ["--show-error-end"]

        result = _run_tool_on_document(document, extra_args=extra_args)

        # Check for misconfiguration before staleness check so warnings
        # are surfaced even if this run is superseded by a newer one.
        if result and result.stderr:
            _check_for_misconfiguration(result.stderr)

        # If a newer lint request arrived while we were running, discard
        # these stale results — the newer request will publish its own.
        with _lint_versions_lock:
            if _lint_versions.get(document.uri, 0) != lint_version:
                log_to_output(
                    f"Discarding stale lint results for {document.uri} "
                    f"(version {lint_version} superseded by "
                    f"{_lint_versions[document.uri]})"
                )
                return []

        # Some mypy modes (e.g., non_interactive) emit diagnostics on stderr.
        # Prefer parsing combined output so we don't miss errors when stdout is empty.
        if result and (result.stdout or result.stderr):
            combined_output = "\n".join(
                [s for s in [result.stdout or "", result.stderr or ""] if s]
            )
            # Keep existing stdout logging for consistency; stderr is logged separately above.
            if result.stdout:
                log_to_output(f"{document.uri} :\r\n{result.stdout}")
            parse_results = _parse_output_using_regex(
                combined_output, settings["severity"]
            )
            reportingScope = settings["reportingScope"]
            for file_path, diagnostics in parse_results.items():
                is_file_same_as_document = utils.is_same_path(file_path, document.path)
                # skip output from other documents
                # (mypy will follow imports, so may include errors found in other
                # documents; this is fine/correct, we just need to account for it).
                if reportingScope == "file" and is_file_same_as_document:
                    LSP_SERVER.text_document_publish_diagnostics(
                        lsp.PublishDiagnosticsParams(
                            uri=document.uri, diagnostics=diagnostics
                        )
                    )
                elif reportingScope in ("workspace", "custom"):
                    _reported_file_paths.add(file_path)
                    uri = uris.from_fs_path(file_path)
                    LSP_SERVER.text_document_publish_diagnostics(
                        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
                    )

            if reportingScope == "file":
                if _is_empty_diagnostics(document.path, parse_results):
                    # Ensure that if nothing is returned for this document, at least
                    # an empty diagnostic is returned to clear any old errors out.
                    _clear_diagnostics(document)

            if reportingScope in ("workspace", "custom"):
                for file_path in _reported_file_paths:
                    if file_path not in parse_results:
                        uri = uris.from_fs_path(file_path)
                        LSP_SERVER.text_document_publish_diagnostics(
                            lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[])
                        )
        else:
            _clear_diagnostics(document)
    except Exception:
        log_error(f"Linting failed with error:\r\n{traceback.format_exc()}")
    return []


def _get_group_dict(line: str) -> Optional[Dict[str, str | None]]:
    match = utils.DIAGNOSTIC_RE.match(line)
    if match:
        return match.groupdict()

    return None


def _parse_output_using_regex(
    content: str, severity: Dict[str, str]
) -> Dict[str, List[lsp.Diagnostic]]:
    lines: List[str] = content.splitlines()
    diagnostics: Dict[str, List[lsp.Diagnostic]] = {}

    notes = []
    see_href = None

    for i, line in enumerate(lines):
        if line.startswith("'") and line.endswith("'"):
            line = line[1:-1]

        # Defensive: strip whitespace before matching, even though the regex
        # handles trailing whitespace with \s*$. This provides extra robustness.
        data = _get_group_dict(line.strip())

        if not data:
            continue

        filepath = utils.absolute_path(data["filepath"])
        type_ = data.get("type")
        code = data.get("code")

        if type_ == "note":
            if see_href is None and data["message"].startswith(utils.SEE_HREF_PREFIX):
                see_href = data["message"][utils.SEE_PREFIX_LEN :]

            notes.append(data["message"])

            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_data = _get_group_dict(next_line)
                if (
                    next_data
                    and next_data["type"] == "note"
                    and next_data["location"] == data["location"]
                ):
                    # the note is not finished yet
                    continue

            message = "\n".join(notes)
            href = see_href
        else:
            message = data["message"]
            href = utils.ERROR_CODE_BASE_URL + code if code else None

        start_line = int(data["line"])
        start_char = int(data["char"] if data["char"] is not None else 1)

        end_line = data["end_line"]
        end_char = data["end_char"]

        end_line = int(end_line) if end_line is not None else start_line
        end_char = int(end_char) + 1 if end_char is not None else start_char

        start = lsp.Position(
            line=max(start_line - utils.LINE_OFFSET, 0),
            character=start_char - utils.CHAR_OFFSET,
        )

        end = lsp.Position(
            line=max(end_line - utils.LINE_OFFSET, 0),
            character=end_char - utils.CHAR_OFFSET,
        )

        diagnostic = lsp.Diagnostic(
            range=lsp.Range(
                start=start,
                end=end,
            ),
            message=message,
            severity=_get_severity(code or "", data["type"], severity),
            code=code if code else utils.NOTE_CODE if see_href else None,
            code_description=lsp.CodeDescription(href=href) if href else None,
            source=TOOL_DISPLAY,
        )
        if filepath in diagnostics:
            diagnostics[filepath].append(diagnostic)
        else:
            diagnostics[filepath] = [diagnostic]

        notes = []
        see_href = None

    return diagnostics


def _get_severity(
    code: str, code_type: str, severity: Dict[str, str]
) -> lsp.DiagnosticSeverity:
    value = severity.get(code, None) or severity.get(code_type, "Error")
    try:
        return lsp.DiagnosticSeverity[value]
    except KeyError:
        pass

    return lsp.DiagnosticSeverity.Information


# **********************************************************
# Linting features end here
# **********************************************************


# **********************************************************
# Required Language Server Initialization and Exit handlers.
# **********************************************************
@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: lsp.InitializeParams) -> None:
    """LSP handler for initialize request."""
    import_strategy = os.getenv("LS_IMPORT_STRATEGY", "useBundled")
    update_sys_path(os.getcwd(), import_strategy)
    tool_server.apply_settings(params)
    settings = (params.initialization_options or {}).get("settings")

    # Add extra paths to sys.path
    setting = tool_server.get_settings_by_path(pathlib.Path(os.getcwd()))
    for extra in setting.get("extraPaths", []):
        update_sys_path(extra, import_strategy)

    tool_server.log_startup_info(settings)

    global DMYPY_STATUS_FILE_ROOT
    if "DMYPY_STATUS_FILE_ROOT" in os.environ:
        DMYPY_STATUS_FILE_ROOT = (
            pathlib.Path(os.environ["DMYPY_STATUS_FILE_ROOT"]) / ".vscode.dmypy_status"
        )
    else:
        DMYPY_STATUS_FILE_ROOT = (
            pathlib.Path(tempfile.gettempdir()) / ".vscode.dmypy_status"
        )

    if not DMYPY_STATUS_FILE_ROOT.exists():
        DMYPY_STATUS_FILE_ROOT.mkdir(parents=True)
        GIT_IGNORE_FILE = DMYPY_STATUS_FILE_ROOT / ".gitignore"
        if not GIT_IGNORE_FILE.exists():
            GIT_IGNORE_FILE.write_text("*", encoding="utf-8")

    _log_version_info()


@LSP_SERVER.feature(lsp.EXIT)
def on_exit(_params: Optional[Any] = None) -> None:
    """Handle clean up on exit."""
    for settings in WORKSPACE_SETTINGS.values():
        mypy_info = get_mypy_info(settings)
        if mypy_info and mypy_info.is_daemon:
            try:
                _run_dmypy_command([], copy.deepcopy(settings), "kill")
            except Exception:
                pass


@LSP_SERVER.feature(lsp.SHUTDOWN)
def on_shutdown(_params: Optional[Any] = None) -> None:
    """Handle clean up on shutdown."""
    for settings in WORKSPACE_SETTINGS.values():
        mypy_info = get_mypy_info(settings)
        if mypy_info and mypy_info.is_daemon:
            try:
                _run_dmypy_command([], copy.deepcopy(settings), "stop")
            except Exception:
                pass


def _log_version_info() -> None:
    for settings in WORKSPACE_SETTINGS.values():
        code_workspace = settings["workspaceFS"]
        mypy_info = get_mypy_info(settings)
        if mypy_info is None:
            continue
        actual_version = mypy_info.version
        min_version = parse_version(MIN_VERSION)

        if actual_version < min_version:
            log_error(
                f"Version of linter running for {code_workspace} is NOT supported:\r\n"
                f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
            )
        else:
            log_to_output(
                f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
            )


# *****************************************************
# Internal functional and settings management APIs.
# Thin wrappers delegating to ToolServer for backward compatibility.
# *****************************************************
def _get_global_defaults():
    return tool_server.get_global_defaults()


def _update_workspace_settings(settings):
    tool_server.update_workspace_settings(settings)


def _get_settings_by_path(file_path: pathlib.Path):
    return tool_server.get_settings_by_path(file_path)


def _get_document_key(document: TextDocument):
    return tool_server.get_document_key(document)


def _get_settings_by_document(document: TextDocument | None):
    return tool_server.get_settings_by_document(document)


# *****************************************************
# Internal execution APIs.
# *****************************************************
def _get_dmypy_args(settings: Dict[str, Any], command: str) -> List[str]:
    """Returns dmypy args for the given command.
    Example:
    For 'run' command returns ['--status-file', '/tmp/dmypy_status.json', 'run', '--']

    Allowed commands:
    - start   : Start daemon
    - restart : Restart daemon (stop or kill followed by start)
    - status  : Show daemon status
    - stop    : Stop daemon (asks it politely to go away)
    - kill    : Kill daemon (kills the process)
    - check   : Check some files (requires daemon)
    - run     : Check some files, [re]starting daemon if necessary
    - recheck : Re-check the previous list of files, with optional modifications (requires daemon)
    - suggest : Suggest a signature or show call sites for a specific function
    - inspect : Locate and statically inspect expression(s)
    - hang    : Hang for 100 seconds
    - daemon  : Run daemon in foreground
    """
    key = normalize_path(settings["workspaceFS"])
    valid_commands = [
        "start",
        "restart",
        "status",
        "stop",
        "kill",
        "check",
        "run",
        "recheck",
        "suggest",
        "inspect",
        "hang",
        "daemon",
    ]
    if command not in valid_commands:
        log_error(f"Invalid dmypy command: {command}")
        raise ValueError(f"Invalid dmypy command: {command}")

    if key not in DMYPY_ARGS:
        daemon_status_file = settings.get("daemonStatusFile", None)
        if daemon_status_file:
            STATUS_FILE_NAME = daemon_status_file
        else:
            STATUS_FILE_NAME = os.fspath(
                DMYPY_STATUS_FILE_ROOT / f"status-{str(uuid.uuid4())}.json"
            )
        args = ["--status-file", STATUS_FILE_NAME]
        DMYPY_ARGS[key] = args

    if command in ["start", "restart", "status", "stop", "kill"]:
        return DMYPY_ARGS[key] + [command]

    return DMYPY_ARGS[key] + [command, "--"]


def _get_env_vars(settings: Dict[str, Any]) -> Dict[str, str]:
    new_env = {
        "PYTHONUTF8": "1",
    }
    if settings.get("extraPaths", []):
        mypy_path = os.environ.get("MYPYPATH", "").split(os.pathsep)
        mypy_path += settings.get("extraPaths", [])
        new_env["MYPYPATH"] = os.pathsep.join([p for p in mypy_path if p])

    if settings.get("importStrategy") == "useBundled":
        pythonpath = os.environ.get("PYTHONPATH", "").split(os.pathsep)
        pythonpath = [BUNDLED_LIBS] + pythonpath
        new_env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    return new_env


def get_cwd(settings: Dict[str, Any], document: Optional[TextDocument]) -> str:
    """Returns cwd for the given settings and document.

    Resolves the following VS Code file-related variable substitutions when
    a document is available:

    - ``${file}`` – absolute path of the current document.
    - ``${fileBasename}`` – file name with extension (e.g. ``foo.py``).
    - ``${fileBasenameNoExtension}`` – file name without extension (e.g. ``foo``).
    - ``${fileExtname}`` – file extension including the dot (e.g. ``.py``).
    - ``${fileDirname}`` – directory containing the current document.
    - ``${fileDirnameBasename}`` – name of the directory containing the document.
    - ``${relativeFile}`` – document path relative to the workspace root.
    - ``${relativeFileDirname}`` – document directory relative to the workspace root.
    - ``${fileWorkspaceFolder}`` – workspace root folder for the document.

    Variables that do not depend on the document (``${workspaceFolder}``,
    ``${userHome}``, ``${cwd}``) are pre-resolved by the TypeScript client.

    The special mypy-specific value ``${nearestConfig}`` walks up the directory
    tree from the document's location to find the nearest mypy configuration file
    (mypy.ini, .mypy.ini, pyproject.toml, setup.cfg).

    If no document is available and the value contains any unresolvable
    file-variable, the workspace root is returned as a fallback.
    """
    cwd = settings.get("cwd", settings["workspaceFS"])
    workspace_fs = settings["workspaceFS"]

    # mypy-specific: walk up to find nearest mypy configuration file
    if cwd == "${nearestConfig}":
        if not document or not document.path:
            return workspace_fs
        workspaceFolder = pathlib.Path(workspace_fs)
        candidate = pathlib.Path(document.path).parent
        check_for = ["mypy.ini", ".mypy.ini", "pyproject.toml", "setup.cfg"]
        # until we leave the workspace
        while candidate.is_relative_to(workspaceFolder):
            for n in check_for:
                candidate_file = candidate / n
                if candidate_file.is_file():
                    log_to_output(
                        f"found {n}, using {candidate}", lsp.MessageType.Debug
                    )
                    return os.fspath(candidate)
            # starting from the current file and working our way up
            else:
                candidate = candidate.parent
        else:
            log_to_output(
                f"failed to find {', '.join(check_for)}; using workspace root",
                lsp.MessageType.Debug,
            )
            return workspace_fs

    return tool_server.get_cwd(settings, document)


def _run_tool_on_document(
    document: TextDocument,
    extra_args: Sequence[str] = None,
) -> RunResult | None:
    """Runs tool on the given document.

    if use_stdin is true then contents of the document is passed to the
    tool via stdin.
    """
    if extra_args is None:
        extra_args = []

    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(tool_server.get_settings_by_document(document))

    cwd = get_cwd(settings, document)

    mypy_info = get_mypy_info(settings)

    if settings["path"]:
        argv = settings["path"]
    else:
        argv = settings["interpreter"] or [sys.executable]
        argv += ["-m", "mypy.dmypy" if mypy_info and mypy_info.is_daemon else "mypy"]
    if mypy_info and mypy_info.is_daemon:
        argv += _get_dmypy_args(settings, "run")
    argv += TOOL_ARGS + settings["args"] + extra_args
    if settings["reportingScope"] == "file":
        # pygls normalizes the path to lowercase on windows, but we need to resolve the
        # correct capitalization to avoid https://github.com/python/mypy/issues/18590#issuecomment-2630249041
        argv += [str(pathlib.Path(document.path).resolve())]
        cwd = str(pathlib.Path(cwd).resolve())
    elif settings["reportingScope"] == "workspace":
        argv += [cwd]
    elif settings["reportingScope"] == "custom":
        # Let mypy use files defined by the configuration
        pass

    tool_server.log_to_output(" ".join(argv))
    tool_server.log_to_output(f"CWD Server: {cwd}")
    result = utils.run_path(
        argv=argv,
        cwd=cwd,
        env=_get_env_vars(settings),
    )
    if result.stderr:
        tool_server.log_to_output(result.stderr)

    tool_server.log_to_output(f"{document.uri} :\r\n{result.stdout}")
    return result


def _run_dmypy_command(
    extra_args: Sequence[str], settings: Dict[str, Any], command: str
) -> RunResult:
    mypy_info = get_mypy_info(settings)
    if not mypy_info or not mypy_info.is_daemon:
        log_error(f"dmypy command called in non-daemon context: {command}")
        raise ValueError(f"dmypy command called in non-daemon context: {command}")

    cwd = get_cwd(settings, None)

    if settings["path"]:
        argv = settings["path"]
    else:
        argv = settings["interpreter"] or [sys.executable]
        argv += ["-m", "mypy.dmypy"]

    argv += _get_dmypy_args(settings, command)
    argv += extra_args
    tool_server.log_to_output(" ".join(argv))
    tool_server.log_to_output(f"CWD Server: {cwd}")

    result = utils.run_path(argv=argv, cwd=cwd, env=_get_env_vars(settings))
    if result.stderr:
        tool_server.log_to_output(result.stderr)

    tool_server.log_to_output(f"\r\n{result.stdout}\r\n")
    return result


# *****************************************************
# Logging and notification.
# *****************************************************
def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    tool_server.log_to_output(message, msg_type)


def log_error(message: str) -> None:
    tool_server.log_error(message)


def log_warning(message: str) -> None:
    tool_server.log_warning(message)


def log_always(message: str) -> None:
    tool_server.log_always(message)


# *****************************************************
# Start the server.
# *****************************************************
if __name__ == "__main__":
    LSP_SERVER.start_io()
