# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Utility functions and classes for use with running tools over LSP."""
from __future__ import annotations

import contextlib
import io
import os
import pathlib
import runpy
import site
import subprocess
import sys
import sysconfig
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

# Save the working directory used when loading this module
SERVER_CWD = os.getcwd()
CWD_LOCK = threading.Lock()
ERROR_CODE_BASE_URL = "https://mypy.readthedocs.io/en/stable/"
ERROR_CODE_ANCHORS = {
    "attr-defined": "error_code_list.html#check-that-attribute-exists-attr-defined",
    "union-attr": "error_code_list.html#check-that-attribute-exists-in-each-union-item-union-attr",
    "name-defined": "error_code_list.html#check-that-name-is-defined-name-defined",
    "used-before-def": "error_code_list.html#check-that-a-variable-is-not-used-before-it-s-defined-used-before-def",
    "call-arg": "error_code_list.html#check-arguments-in-calls-call-arg",
    "arg-type": "error_code_list.html#check-argument-types-arg-type",
    "call-overload": "error_code_list.html#check-calls-to-overloaded-functions-call-overload",
    "valid-type": "error_code_list.html#check-validity-of-types-valid-type",
    "var-annotated": "error_code_list.html#require-annotation-if-variable-type-is-unclear-var-annotated",
    "override": "error_code_list.html#check-validity-of-overrides-override",
    "return": "error_code_list.html#check-that-function-returns-a-value-return",
    "return-value": "error_code_list.html#check-that-return-value-is-compatible-return-value",
    "assignment": "error_code_list.html#check-types-in-assignment-statement-assignment",
    "method-assign": "error_code_list.html#check-that-assignment-target-is-not-a-method-method-assign",
    "type-var": "error_code_list.html#check-type-variable-values-type-var",
    "operator": "error_code_list.html#check-uses-of-various-operators-operator",
    "index": "error_code_list.html#check-indexing-operations-index",
    "list-item": "error_code_list.html#check-list-items-list-item",
    "dict-item": "error_code_list.html#check-dict-items-dict-item",
    "typeddict-item": "error_code_list.html#check-typeddict-items-typeddict-item",
    "typeddict-unknown-key": "error_code_list.html#check-typeddict-keys-typeddict-unknown-key",
    "has-type": "error_code_list.html#check-that-type-of-target-is-known-has-type",
    "import": "error_code_list.html#check-that-import-target-can-be-found-import",
    "no-redef": "error_code_list.html#check-that-each-name-is-defined-once-no-redef",
    "func-returns-value": "error_code_list.html#check-that-called-function-returns-a-value-func-returns-value",
    "abstract": "error_code_list.html#check-instantiation-of-abstract-classes-abstract",
    "type-abstract": "error_code_list.html#safe-handling-of-abstract-type-object-types-type-abstract",
    "safe-super": "error_code_list.html#check-that-call-to-an-abstract-method-via-super-is-valid-safe-super",
    "valid-newtype": "error_code_list.html#check-the-target-of-newtype-valid-newtype",
    "exit-return": "error_code_list.html#check-the-return-type-of-exit-exit-return",
    "name-match": "error_code_list.html#check-that-naming-is-consistent-name-match",
    "literal-required": "error_code_list.html#check-that-literal-is-used-where-expected-literal-required",
    "no-overload-impl": "error_code_list.html#check-that-overloaded-functions-have-an-implementation-no-overload-impl",
    "unused-coroutine": "error_code_list.html#check-that-coroutine-return-value-is-used-unused-coroutine",
    "assert-type": "error_code_list.html#check-types-in-assert-type-assert-type",
    "truthy-function": "error_code_list.html#check-that-function-isn-t-used-in-boolean-context-truthy-function",
    "str-bytes-safe": "error_code_list.html#check-for-implicit-bytes-coercions-str-bytes-safe",
    "syntax": "error_code_list.html#report-syntax-errors-syntax",
    "misc": "error_code_list.html#miscellaneous-checks-misc",
    "type-arg": "error_code_list2.html#check-that-type-arguments-exist-type-arg",
    "no-untyped-def": "error_code_list2.html#check-that-every-function-has-an-annotation-no-untyped-def",
    "redundant-cast": "error_code_list2.html#check-that-cast-is-not-redundant-redundant-cast",
    "redundant-self": "error_code_list2.html#check-that-methods-do-not-have-redundant-self-annotations-redundant-self",
    "comparison-overlap": "error_code_list2.html#check-that-comparisons-are-overlapping-comparison-overlap",
    "no-untyped-call": "error_code_list2.html#check-that-no-untyped-functions-are-called-no-untyped-call",
    "no-any-return": "error_code_list2.html#check-that-function-does-not-return-any-value-no-any-return",
    "no-any-unimported": "error_code_list2.html#check-that-types-have-no-any-components-due-to-missing-imports-no-any-unimported",
    "unreachable": "error_code_list2.html#check-that-statement-or-expression-is-unreachable-unreachable",
    "redundant-expr": "error_code_list2.html#check-that-expression-is-redundant-redundant-expr",
    "truthy-bool": "error_code_list2.html#check-that-expression-is-not-implicitly-true-in-boolean-context-truthy-bool",
    "truthy-iterable": "error_code_list2.html#check-that-iterable-is-not-implicitly-true-in-boolean-context-truthy-iterable",
    "undefined": "error_code_list2.html#check-that-type-ignore-include-an-error-code-ignore-without-code",
    "unused-awaitable": "error_code_list2.html#check-that-awaitable-return-value-is-used-unused-awaitable"
}


def as_list(content: Union[Any, List[Any], Tuple[Any]]) -> List[Any]:
    """Ensures we always get a list"""
    if isinstance(content, (list, tuple)):
        return list(content)
    return [content]


_site_paths = set(
    str(pathlib.Path(p).resolve())
    for p in (
        as_list(site.getsitepackages())
        + as_list(site.getusersitepackages())
        + list(sysconfig.get_paths().values())
    )
)


def is_same_path(file_path1: str, file_path2: str) -> bool:
    """Returns true if two paths are the same."""
    return pathlib.Path(file_path1) == pathlib.Path(file_path2)


def normalize_path(file_path: str) -> str:
    """Returns normalized path."""
    return str(pathlib.Path(file_path).resolve())


def is_current_interpreter(executable) -> bool:
    """Returns true if the executable path is same as the current interpreter."""
    return is_same_path(executable, sys.executable)


def is_stdlib_file(file_path: str) -> bool:
    """Return True if the file belongs to the standard library."""
    normalized_path = str(pathlib.Path(file_path).resolve())
    return any(normalized_path.startswith(path) for path in _site_paths)


# pylint: disable-next=too-few-public-methods
class RunResult:
    """Object to hold result from running tool."""

    def __init__(
        self, stdout: str, stderr: str, exit_code: Optional[Union[int, str]] = None
    ):
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.exit_code: Optional[Union[int, str]] = exit_code


class CustomIO(io.TextIOWrapper):
    """Custom stream object to replace stdio."""

    name = None

    def __init__(self, name, encoding="utf-8", newline=None):
        self._buffer = io.BytesIO()
        self._buffer.name = name
        super().__init__(self._buffer, encoding=encoding, newline=newline)

    def close(self):
        """Provide this close method which is used by some tools."""
        # This is intentionally empty.

    def get_value(self) -> str:
        """Returns value from the buffer as string."""
        self.seek(0)
        return self.read()


@contextlib.contextmanager
def substitute_attr(obj: Any, attribute: str, new_value: Any):
    """Manage object attributes context when using runpy.run_module()."""
    old_value = getattr(obj, attribute)
    setattr(obj, attribute, new_value)
    yield
    setattr(obj, attribute, old_value)


@contextlib.contextmanager
def redirect_io(stream: str, new_stream):
    """Redirect stdio streams to a custom stream."""
    old_stream = getattr(sys, stream)
    setattr(sys, stream, new_stream)
    yield
    setattr(sys, stream, old_stream)


@contextlib.contextmanager
def change_cwd(new_cwd):
    """Change working directory before running code."""
    os.chdir(new_cwd)
    yield
    os.chdir(SERVER_CWD)


def _run_module(
    module: str, argv: Sequence[str], use_stdin: bool, source: str = None
) -> RunResult:
    """Runs as a module."""
    str_output = CustomIO("<stdout>", encoding="utf-8")
    str_error = CustomIO("<stderr>", encoding="utf-8")
    exit_code = None

    try:
        with substitute_attr(sys, "argv", argv):
            with redirect_io("stdout", str_output):
                with redirect_io("stderr", str_error):
                    if use_stdin and source is not None:
                        str_input = CustomIO("<stdin>", encoding="utf-8", newline="\n")
                        with redirect_io("stdin", str_input):
                            str_input.write(source)
                            str_input.seek(0)
                            runpy.run_module(module, run_name="__main__")
                    else:
                        runpy.run_module(module, run_name="__main__")
    except SystemExit as ex:
        exit_code = ex.code

    return RunResult(str_output.get_value(), str_error.get_value(), exit_code)


def run_module(
    module: str, argv: Sequence[str], use_stdin: bool, cwd: str, source: str = None
) -> RunResult:
    """Runs as a module."""
    with CWD_LOCK:
        if is_same_path(os.getcwd(), cwd):
            return _run_module(module, argv, use_stdin, source)
        with change_cwd(cwd):
            return _run_module(module, argv, use_stdin, source)


def run_path(argv: Sequence[str], cwd: str, env: Dict[str, str] = None) -> RunResult:
    """Runs as an executable."""
    new_env = os.environ.copy()
    if env is not None:
        new_env.update(env)
    result = subprocess.run(
        argv,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        cwd=cwd,
        env=new_env,
    )
    return RunResult(result.stdout, result.stderr, result.returncode)


def run_api(
    callback: Callable[[Sequence[str], Optional[CustomIO]], Tuple[str, str, int]],
    argv: Sequence[str],
    use_stdin: bool,
    cwd: str,
    source: str = None,
) -> RunResult:
    """Run a API."""
    with CWD_LOCK:
        if is_same_path(os.getcwd(), cwd):
            return _run_api(callback, argv, use_stdin, source)
        with change_cwd(cwd):
            return _run_api(callback, argv, use_stdin, source)


def _run_api(
    callback: Callable[[Sequence[str], Optional[CustomIO]], Tuple[str, str, int]],
    argv: Sequence[str],
    use_stdin: bool,
    source: str = None,
) -> RunResult:
    str_output = None
    str_error = None

    try:
        with substitute_attr(sys, "argv", argv):
            if use_stdin and source is not None:
                str_input = CustomIO("<stdin>", encoding="utf-8", newline="\n")
                with redirect_io("stdin", str_input):
                    str_input.write(source)
                    str_input.seek(0)
                    str_output, str_error, exit_code = callback(argv, str_input)
            else:
                str_output, str_error, exit_code = callback(argv, None)
    except SystemExit:
        pass

    return RunResult(str_output, str_error, exit_code)
