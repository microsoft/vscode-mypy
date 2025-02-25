# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Implementation of tool support over LSP."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re
import sys
import sysconfig
import tempfile
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


# **********************************************************
# Update PATH before running anything.
# **********************************************************
def update_environ_path() -> None:
    """Update PATH environment variable with the 'scripts' directory.
    Windows: .venv/Scripts
    Linux/MacOS: .venv/bin
    """
    scripts = sysconfig.get_path("scripts")
    paths_variants = ["Path", "PATH"]

    for var_name in paths_variants:
        if var_name in os.environ:
            paths = os.environ[var_name].split(os.pathsep)
            if scripts not in paths:
                paths.insert(0, scripts)
                os.environ[var_name] = os.pathsep.join(paths)
                break


# Ensure that we can import LSP libraries, and other bundled libraries.
BUNDLE_DIR = pathlib.Path(__file__).parent.parent
BUNDLED_LIBS = os.fspath(BUNDLE_DIR / "libs")
# Always use bundled server files.
update_sys_path(os.fspath(BUNDLE_DIR / "tool"), "useBundled")
update_sys_path(
    BUNDLED_LIBS,
    os.getenv("LS_IMPORT_STRATEGY", "useBundled"),
)
update_environ_path()

# **********************************************************
# Imports needed for the language server goes below this.
# **********************************************************
import lsp_utils as utils
import lsprotocol.types as lsp
from packaging.version import Version
from packaging.version import parse as parse_version
from pygls import server, uris, workspace

WORKSPACE_SETTINGS = {}
GLOBAL_SETTINGS = {}

MAX_WORKERS = 5
LSP_SERVER = server.LanguageServer(
    name="Mypy", version="v0.1.0", max_workers=MAX_WORKERS
)

DMYPY_ARGS = {}
DMYPY_STATUS_FILE_ROOT = None

# **********************************************************
# Tool specific code goes below this.
# **********************************************************
TOOL_MODULE = "mypy"
TOOL_DISPLAY = "Mypy"
TOOL_ARGS = [
    "--no-color-output",
    "--no-error-summary",
    "--show-absolute-path",
    "--show-column-numbers",
    "--show-error-codes",
    "--no-pretty",
]
MIN_VERSION = "1.0.0"

# **********************************************************
# Linting features start here
# **********************************************************


@dataclass
class MypyInfo:
    version: Version
    is_daemon: bool


# Stores infomation of `mypy` executable in various workspaces.
MYPY_INFO_TABLE: Dict[str, MypyInfo] = {}


def get_mypy_info(settings: Dict[str, Any]) -> MypyInfo:
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
        log_to_output(
            f"Error while checking mypy executable:\r\n{traceback.format_exc()}"
        )


def _run_unidentified_tool(
    extra_args: Sequence[str], settings: Dict[str, Any]
) -> utils.RunResult:
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
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    _linting_helper(document)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    """LSP handler for textDocument/didSave request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    _linting_helper(document)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
    """LSP handler for textDocument/didClose request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    settings = _get_settings_by_document(document)
    if settings["reportingScope"] == "file":
        # Publishing empty diagnostics to clear the entries for this file.
        _clear_diagnostics(document)


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


def _clear_diagnostics(document: workspace.Document) -> None:
    LSP_SERVER.publish_diagnostics(document.uri, [])


def _linting_helper(document: workspace.Document) -> None:
    global _reported_file_paths
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

        if settings["reportingScope"] == "file" and utils.is_match(
            settings["ignorePatterns"], document.path
        ):
            log_warning(
                f"Skipping file due to `mypy-type-checker.ignorePatterns` match: {document.path}"
            )
            _clear_diagnostics(document)
            return None

        version = get_mypy_info(settings).version
        if (version.major, version.minor) >= (0, 991) and sys.version_info >= (3, 8):
            extra_args += ["--show-error-end"]

        result = _run_tool_on_document(document, extra_args=extra_args)
        if result and result.stdout:
            log_to_output(f"{document.uri} :\r\n{result.stdout}")
            parse_results = _parse_output_using_regex(
                result.stdout, settings["severity"]
            )
            reportingScope = settings["reportingScope"]
            for file_path, diagnostics in parse_results.items():
                is_file_same_as_document = utils.is_same_path(file_path, document.path)
                # skip output from other documents
                # (mypy will follow imports, so may include errors found in other
                # documents; this is fine/correct, we just need to account for it).
                if reportingScope == "file" and is_file_same_as_document:
                    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)
                elif reportingScope == "workspace":
                    _reported_file_paths.add(file_path)
                    uri = uris.from_fs_path(file_path)
                    LSP_SERVER.publish_diagnostics(uri, diagnostics)

            if reportingScope == "file":
                if _is_empty_diagnostics(document.path, parse_results):
                    # Ensure that if nothing is returned for this document, at least
                    # an empty diagnostic is returned to clear any old errors out.
                    _clear_diagnostics(document)

            if reportingScope == "workspace":
                for file_path in _reported_file_paths:
                    if file_path not in parse_results:
                        uri = uris.from_fs_path(file_path)
                        LSP_SERVER.publish_diagnostics(uri, [])
        else:
            _clear_diagnostics(document)
    except Exception:
        LSP_SERVER.show_message_log(
            f"Linting failed with error:\r\n{traceback.format_exc()}",
            lsp.MessageType.Error,
        )
    return []


DIAGNOSTIC_RE = re.compile(
    r"^(?P<location>(?P<filepath>..[^:]*):(?P<line>\d+)(?::(?P<char>\d+))?(?::(?P<end_line>\d+):(?P<end_char>\d+))?): (?P<type>\w+): (?P<message>.*?)(?:  )?(?:\[(?P<code>[\w-]+)\])?$"
)


def _get_group_dict(line: str) -> Optional[Dict[str, str | None]]:
    match = DIAGNOSTIC_RE.match(line)
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

        data = _get_group_dict(line)

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
    log_to_output(f"CWD Server: {os.getcwd()}")
    import_strategy = os.getenv("LS_IMPORT_STRATEGY", "useBundled")
    update_sys_path(os.getcwd(), import_strategy)

    GLOBAL_SETTINGS.update(**params.initialization_options.get("globalSettings", {}))

    settings = params.initialization_options["settings"]
    _update_workspace_settings(settings)
    log_to_output(
        f"Settings used to run Server:\r\n{json.dumps(settings, indent=4, ensure_ascii=False)}\r\n"
    )
    log_to_output(
        f"Global settings:\r\n{json.dumps(GLOBAL_SETTINGS, indent=4, ensure_ascii=False)}\r\n"
    )

    # Add extra paths to sys.path
    setting = _get_settings_by_path(pathlib.Path(os.getcwd()))
    for extra in setting.get("extraPaths", []):
        update_sys_path(extra, import_strategy)

    paths = "\r\n   ".join(sys.path)
    log_to_output(f"sys.path used to run Server:\r\n   {paths}")

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
        if get_mypy_info(settings).is_daemon:
            try:
                _run_dmypy_command([], copy.deepcopy(settings), "kill")
            except Exception:
                pass


@LSP_SERVER.feature(lsp.SHUTDOWN)
def on_shutdown(_params: Optional[Any] = None) -> None:
    """Handle clean up on shutdown."""
    for settings in WORKSPACE_SETTINGS.values():
        if get_mypy_info(settings).is_daemon:
            try:
                _run_dmypy_command([], copy.deepcopy(settings), "stop")
            except Exception:
                pass


def _log_version_info() -> None:
    for settings in WORKSPACE_SETTINGS.values():
        code_workspace = settings["workspaceFS"]
        actual_version = get_mypy_info(settings).version
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
# *****************************************************
def _get_global_defaults():
    return {
        "path": GLOBAL_SETTINGS.get("path", []),
        "interpreter": GLOBAL_SETTINGS.get("interpreter", [sys.executable]),
        "args": GLOBAL_SETTINGS.get("args", []),
        "severity": GLOBAL_SETTINGS.get(
            "severity",
            {
                "error": "Error",
                "note": "Information",
            },
        ),
        "ignorePatterns": GLOBAL_SETTINGS.get("ignorePatterns", []),
        "importStrategy": GLOBAL_SETTINGS.get("importStrategy", "useBundled"),
        "showNotifications": GLOBAL_SETTINGS.get("showNotifications", "off"),
        "extraPaths": GLOBAL_SETTINGS.get("extraPaths", []),
        "reportingScope": GLOBAL_SETTINGS.get("reportingScope", "file"),
        "preferDaemon": GLOBAL_SETTINGS.get("preferDaemon", True),
        "daemonStatusFile": GLOBAL_SETTINGS.get("daemonStatusFile", ""),
    }


def _update_workspace_settings(settings):
    if not settings:
        key = utils.normalize_path(os.getcwd())
        WORKSPACE_SETTINGS[key] = {
            "cwd": key,
            "workspaceFS": key,
            "workspace": uris.from_fs_path(key),
            **_get_global_defaults(),
        }
        return

    for setting in settings:
        key = utils.normalize_path(uris.to_fs_path(setting["workspace"]))
        WORKSPACE_SETTINGS[key] = {
            **setting,
            "workspaceFS": key,
        }


def _get_settings_by_path(file_path: pathlib.Path):
    workspaces = {s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()}

    while file_path != file_path.parent:
        str_file_path = utils.normalize_path(file_path)
        if str_file_path in workspaces:
            return WORKSPACE_SETTINGS[str_file_path]
        file_path = file_path.parent

    setting_values = list(WORKSPACE_SETTINGS.values())
    return setting_values[0]


def _get_document_key(document: workspace.Document):
    if WORKSPACE_SETTINGS:
        document_workspace = pathlib.Path(document.path)
        workspaces = {s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()}

        # Find workspace settings for the given file.
        while document_workspace != document_workspace.parent:
            norm_path = utils.normalize_path(document_workspace)
            if norm_path in workspaces:
                return norm_path
            document_workspace = document_workspace.parent

    return None


def _get_settings_by_document(document: workspace.Document | None):
    if document is None or document.path is None:
        return list(WORKSPACE_SETTINGS.values())[0]

    key = _get_document_key(document)
    if key is None:
        # This is either a non-workspace file or there is no workspace.
        key = utils.normalize_path(pathlib.Path(document.path).parent)
        return {
            "cwd": key,
            "workspaceFS": key,
            "workspace": uris.from_fs_path(key),
            **_get_global_defaults(),
        }

    return WORKSPACE_SETTINGS[str(key)]


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
    key = utils.normalize_path(settings["workspaceFS"])
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
        if settings["daemonStatusFile"]:
            STATUS_FILE_NAME = settings["daemonStatusFile"]
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


def get_cwd(settings: Dict[str, Any], document: Optional[workspace.Document]) -> str:
    """Returns cwd for the given settings and document."""
    # this happens when running dmypy.
    if document is None:
        return settings["workspaceFS"]

    if settings["cwd"] == "${workspaceFolder}":
        return settings["workspaceFS"]

    if settings["cwd"] == "${fileDirname}":
        return os.fspath(pathlib.Path(document.path).parent)

    if settings["cwd"] == "${nearestConfig}":
        workspaceFolder = pathlib.Path(settings["workspaceFS"])
        candidate = pathlib.Path(document.path).parent
        # check if pyproject exists
        check_for = ["pyproject.toml", "mypy.ini"]
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
            return settings["workspaceFS"]

    return settings["cwd"]


def _run_tool_on_document(
    document: workspace.Document,
    extra_args: Sequence[str] = None,
) -> utils.RunResult | None:
    """Runs tool on the given document.

    if use_stdin is true then contents of the document is passed to the
    tool via stdin.
    """
    if extra_args is None:
        extra_args = []

    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(_get_settings_by_document(document))

    cwd = get_cwd(settings, document)

    if settings["path"]:
        argv = settings["path"]
    else:
        argv = settings["interpreter"] or [sys.executable]
        argv += ["-m", "mypy.dmypy" if get_mypy_info(settings).is_daemon else "mypy"]
    if get_mypy_info(settings).is_daemon:
        argv += _get_dmypy_args(settings, "run")
    argv += TOOL_ARGS + settings["args"] + extra_args
    if settings["reportingScope"] == "file":
        # pygls normalizes the path to lowercase on windows, but we need to resolve the
        # correct capitalization to avoid https://github.com/python/mypy/issues/18590#issuecomment-2630249041
        argv += [str(pathlib.Path(document.path).resolve())]
        cwd = str(pathlib.Path(cwd).resolve())
    else:
        argv += [cwd]

    log_to_output(" ".join(argv))
    log_to_output(f"CWD Server: {cwd}")
    result = utils.run_path(
        argv=argv,
        cwd=cwd,
        env=_get_env_vars(settings),
    )
    if result.stderr:
        log_to_output(result.stderr)

    log_to_output(f"{document.uri} :\r\n{result.stdout}")
    return result


def _run_dmypy_command(
    extra_args: Sequence[str], settings: Dict[str, Any], command: str
) -> utils.RunResult:
    if not get_mypy_info(settings).is_daemon:
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
    log_to_output(" ".join(argv))
    log_to_output(f"CWD Server: {cwd}")

    result = utils.run_path(argv=argv, cwd=cwd, env=_get_env_vars(settings))
    if result.stderr:
        log_to_output(result.stderr)

    log_to_output(f"\r\n{result.stdout}\r\n")
    return result


# *****************************************************
# Logging and notification.
# *****************************************************
def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    LSP_SERVER.show_message_log(message, msg_type)


def log_error(message: str) -> None:
    LSP_SERVER.show_message_log(message, lsp.MessageType.Error)
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["onError", "onWarning", "always"]:
        LSP_SERVER.show_message(message, lsp.MessageType.Error)


def log_warning(message: str) -> None:
    LSP_SERVER.show_message_log(message, lsp.MessageType.Warning)
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["onWarning", "always"]:
        LSP_SERVER.show_message(message, lsp.MessageType.Warning)


def log_always(message: str) -> None:
    LSP_SERVER.show_message_log(message, lsp.MessageType.Info)
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["always"]:
        LSP_SERVER.show_message(message, lsp.MessageType.Info)


# *****************************************************
# Start the server.
# *****************************************************
if __name__ == "__main__":
    LSP_SERVER.start_io()
