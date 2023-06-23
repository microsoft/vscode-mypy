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
import tempfile
import traceback
import uuid
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
BUNDLED_LIBS = os.fspath(pathlib.Path(__file__).parent.parent / "libs")
update_sys_path(
    BUNDLED_LIBS,
    os.getenv("LS_IMPORT_STRATEGY", "useBundled"),
)

# **********************************************************
# Imports needed for the language server goes below this.
# **********************************************************
import lsp_utils as utils
import lsprotocol.types as lsp
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
    "--show-column-numbers",
    "--show-error-code",
    "--no-pretty",
]
MIN_VERSION = "1.0.0"

# **********************************************************
# Linting features start here
# **********************************************************
# Captures version of `mypy` in various workspaces.
VERSION_TABLE: Dict[str, (int, int, int)] = {}


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
    """LSP handler for textDocument/didOpen request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    """LSP handler for textDocument/didSave request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
    """LSP handler for textDocument/didClose request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    # Publishing empty diagnostics to clear the entries for this file.
    LSP_SERVER.publish_diagnostics(document.uri, [])


def _linting_helper(document: workspace.Document) -> list[lsp.Diagnostic]:
    try:
        extra_args = []

        code_workspace = _get_settings_by_document(document)["workspaceFS"]
        if VERSION_TABLE.get(code_workspace, None):
            major, minor, _ = VERSION_TABLE[code_workspace]
            if (major, minor) >= (0, 991):
                extra_args += ["--show-error-end"]

        result = _run_tool_on_document(document, extra_args=extra_args)
        if result and result.stdout:
            log_to_output(f"{document.uri} :\r\n{result.stdout}")

            # deep copy here to prevent accidentally updating global settings.
            settings = copy.deepcopy(_get_settings_by_document(document))
            return _parse_output_using_regex(result.stdout, settings["severity"])
    except Exception:
        LSP_SERVER.show_message_log(
            f"Linting failed with error:\r\n{traceback.format_exc()}",
            lsp.MessageType.Error,
        )
    return []


DIAGNOSTIC_RE = re.compile(
    r"^(?P<location>(?P<filepath>..[^:]*):(?P<line>\d+):(?P<char>\d+)(?::(?P<end_line>\d+):(?P<end_char>\d+))?): (?P<type>\w+): (?P<message>.*?)(?:  \[(?P<code>[\w-]+)\])?$"
)


def _get_group_dict(line: str) -> Optional[Dict[str, str]]:
    match = DIAGNOSTIC_RE.match(line)
    if match:
        return match.groupdict()

    return None


def _parse_output_using_regex(
    content: str, severity: Dict[str, str]
) -> list[lsp.Diagnostic]:
    lines: list[str] = content.splitlines()
    diagnostics: list[lsp.Diagnostic] = []

    notes = []
    see_href = None

    for i, line in enumerate(lines):
        if line.startswith("'") and line.endswith("'"):
            line = line[1:-1]

        data = _get_group_dict(line)

        if data:
            type_ = data["type"]
            code = data.get("code", None)

            if type_ == "note":
                if see_href is None and data["message"].startswith(
                    utils.SEE_HREF_PREFIX
                ):
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
            start_char = int(data["char"])

            start = lsp.Position(
                line=max(start_line - utils.LINE_OFFSET, 0),
                character=start_char - utils.CHAR_OFFSET,
            )

            end_line = int(data.get("end_line", start.line))
            end_char = int(data.get("end_char", start.character))

            if end_char > start_char:
                # if the range is not empty, we need to include the last character
                # if the range is empty, vscode automatically ranges the surrounding ident
                end_char += 1

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
            diagnostics.append(diagnostic)

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
    for value in WORKSPACE_SETTINGS.values():
        try:
            settings = copy.deepcopy(value)
            _run_tool([], settings, "kill")
        except Exception:
            pass


@LSP_SERVER.feature(lsp.SHUTDOWN)
def on_shutdown(_params: Optional[Any] = None) -> None:
    """Handle clean up on shutdown."""
    for value in WORKSPACE_SETTINGS.values():
        try:
            settings = copy.deepcopy(value)
            _run_tool([], settings, "stop")
        except Exception:
            pass


def _log_version_info() -> None:
    for value in WORKSPACE_SETTINGS.values():
        try:
            from packaging.version import parse as parse_version

            settings = copy.deepcopy(value)
            result = _run_tool(["--version"], settings, "version")
            code_workspace = settings["workspaceFS"]
            log_to_output(
                f"Version info for linter running for {code_workspace}:\r\n{result.stdout}"
            )

            # This is text we get from running `mypy --version`
            # mypy 1.0.0 (compiled: yes) <--- This is the version we want.
            first_line = result.stdout.splitlines(keepends=False)[0]
            actual_version = first_line.split(" ")[1]

            # Update the key with a flag indicating `dmypy`
            value["dmypy"] = first_line.startswith("dmypy")

            version = parse_version(actual_version)
            min_version = parse_version(MIN_VERSION)
            VERSION_TABLE[code_workspace] = (
                version.major,
                version.minor,
                version.micro,
            )

            if version < min_version:
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
        except:  # noqa: E722
            log_to_output(
                f"Error while detecting mypy version:\r\n{traceback.format_exc()}"
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
        "importStrategy": GLOBAL_SETTINGS.get("importStrategy", "useBundled"),
        "showNotifications": GLOBAL_SETTINGS.get("showNotifications", "off"),
        "extraPaths": GLOBAL_SETTINGS.get("extraPaths", []),
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


def _run_tool_on_document(
    document: workspace.Document,
    extra_args: Sequence[str] = [],
) -> utils.RunResult | None:
    """Runs tool on the given document.

    if use_stdin is true then contents of the document is passed to the
    tool via stdin.
    """
    if str(document.uri).startswith("vscode-notebook-cell"):
        # We don't support running mypy on notebook cells.
        log_to_output("Skipping mypy on notebook cells.")
        return None

    if utils.is_stdlib_file(document.path):
        log_to_output("Skipping mypy on stdlib file: " + document.path)
        return None

    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(_get_settings_by_document(document))
    cwd = settings["cwd"]

    if settings["path"]:
        argv = settings["path"]
        if settings.get("dmypy"):
            argv += _get_dmypy_args(settings, "run")
    else:
        # Otherwise, we run mypy via dmypy.
        if settings["interpreter"]:
            argv = settings["interpreter"]
        else:
            argv = [sys.executable]
        argv += ["-m", "mypy.dmypy"]
        argv += _get_dmypy_args(settings, "run")

    argv += TOOL_ARGS + settings["args"] + extra_args + [document.path]

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


def _run_tool(
    extra_args: Sequence[str], settings: Dict[str, Any], command: str
) -> utils.RunResult:
    """Runs tool."""
    cwd = settings["cwd"]

    if settings["path"]:
        argv = settings["path"]
        if settings.get("dmypy"):
            if command == "version":
                # version check does not need dmypy command or
                # status file arguments.
                pass
            else:
                argv += _get_dmypy_args(settings, command)
    else:
        # Otherwise, we run mypy via dmypy.
        if settings["interpreter"]:
            argv = settings["interpreter"]
        else:
            argv = [sys.executable]

        argv += ["-m", "mypy.dmypy"]
        if command == "version":
            # version check does not need dmypy command or
            # status file arguments.
            pass
        else:
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
