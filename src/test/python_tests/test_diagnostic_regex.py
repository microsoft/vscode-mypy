# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for diagnostic regex parsing in lsp_server.

Mock LSP dependencies and sys.path setup are provided by conftest.py.
"""

import pytest
from lsp_utils import DIAGNOSTIC_RE


def _get_group_dict(line: str):
    """Helper function to get match groups from a line."""
    match = DIAGNOSTIC_RE.match(line)
    if match:
        return match.groupdict()
    return None


@pytest.mark.parametrize(
    "line, expected",
    [
        pytest.param(
            '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var]',
            {
                "code": "type-var",
                "message": 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"',
                "line": "14",
                "char": "16",
                "end_line": "19",
                "end_char": "5",
                "type": "error",
            },
            id="type-var",
        ),
        pytest.param(
            '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var] ',
            {
                "code": "type-var",
                "message": 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"',
            },
            id="trailing-space",
        ),
        pytest.param(
            '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var]\t',
            {
                "code": "type-var",
                "message": 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"',
            },
            id="trailing-tab",
        ),
        pytest.param(
            '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var]   ',
            {
                "code": "type-var",
                "message": 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"',
            },
            id="trailing-multiple-spaces",
        ),
        pytest.param(
            "/path/to/file.py:14:16: error: Some error message",
            {
                "code": None,
                "message": "Some error message",
                "line": "14",
                "char": "16",
            },
            id="without-error-code",
        ),
        pytest.param(
            '/path/to/file.py:2:6:2:7: error: Name "x" is not defined  [name-defined]',
            {
                "code": "name-defined",
                "message": 'Name "x" is not defined',
                "line": "2",
                "char": "6",
                "end_line": "2",
                "end_char": "7",
            },
            id="name-defined",
        ),
        pytest.param(
            "/path/to/file.py:5:10: note: See https://mypy.readthedocs.io/en/stable",
            {
                "type": "note",
                "message": "See https://mypy.readthedocs.io/en/stable",
                "code": None,
            },
            id="note-type",
        ),
        pytest.param(
            "/path/to/file.py:10: error: Some error without column  [misc]",
            {
                "code": "misc",
                "message": "Some error without column",
                "line": "10",
                "char": None,
                "end_line": None,
                "end_char": None,
            },
            id="without-column",
        ),
    ],
)
def test_diagnostic_regex_parsing(line, expected):
    """DIAGNOSTIC_RE correctly extracts fields from mypy output lines."""
    data = _get_group_dict(line)
    assert data is not None, f"Regex should match: {line}"
    for key, value in expected.items():
        assert data[key] == value, f"Expected {key}={value!r}, got {data[key]!r}"
