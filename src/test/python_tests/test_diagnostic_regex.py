# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Unit tests for diagnostic regex parsing in lsp_server.
"""

import re

# NOTE: This regex pattern is duplicated from bundled/tool/lsp_server.py
# to allow for isolated unit testing without needing to import the entire
# lsp_server module (which has dependencies on lsprotocol and other modules).
# If the pattern in lsp_server.py is updated, this must be updated as well.
DIAGNOSTIC_RE = re.compile(
    r"^(?P<location>(?P<filepath>..[^:]*):(?P<line>\d+)(?::(?P<char>\d+))?(?::(?P<end_line>\d+):(?P<end_char>\d+))?): (?P<type>\w+): (?P<message>.*?)(?:\s{2}\[(?P<code>[\w-]+)\])?\s*$"
)


def _get_group_dict(line: str):
    """Helper function to get match groups from a line."""
    match = DIAGNOSTIC_RE.match(line)
    if match:
        return match.groupdict()
    return None


def test_diagnostic_regex_with_type_var_error():
    """Test that [type-var] errors are correctly parsed."""
    line = '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var]'

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the type-var error line"
    assert data["code"] == "type-var", f"Expected code 'type-var', got {data['code']}"
    assert (
        data["message"]
        == 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"'
    ), f"Message should not include the error code, got: {data['message']}"
    assert data["line"] == "14"
    assert data["char"] == "16"
    assert data["end_line"] == "19"
    assert data["end_char"] == "5"
    assert data["type"] == "error"


def test_diagnostic_regex_with_trailing_space():
    """Test that lines with trailing space after error code are correctly parsed."""
    line = '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var] '

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the line with trailing space"
    assert data["code"] == "type-var", f"Expected code 'type-var', got {data['code']}"
    assert (
        data["message"]
        == 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"'
    ), f"Message should not include the error code or trailing whitespace, got: {data['message']}"


def test_diagnostic_regex_with_trailing_tab():
    """Test that lines with trailing tab after error code are correctly parsed."""
    line = '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var]\t'

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the line with trailing tab"
    assert data["code"] == "type-var", f"Expected code 'type-var', got {data['code']}"
    assert (
        data["message"]
        == 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"'
    ), f"Message should not include the error code or trailing whitespace, got: {data['message']}"


def test_diagnostic_regex_with_multiple_trailing_spaces():
    """Test that lines with multiple trailing spaces are correctly parsed."""
    line = '/path/to/condition.py:14:16:19:5: error: Value of type variable "InstanceT" of "Metadata" cannot be "Condition"  [type-var]   '

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the line with multiple trailing spaces"
    assert data["code"] == "type-var", f"Expected code 'type-var', got {data['code']}"
    assert (
        data["message"]
        == 'Value of type variable "InstanceT" of "Metadata" cannot be "Condition"'
    ), f"Message should not include the error code or trailing whitespace, got: {data['message']}"


def test_diagnostic_regex_without_error_code():
    """Test that lines without error code are correctly parsed."""
    line = "/path/to/file.py:14:16: error: Some error message"

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the line without error code"
    assert data["code"] is None, f"Expected code to be None, got {data['code']}"
    assert data["message"] == "Some error message"
    assert data["line"] == "14"
    assert data["char"] == "16"


def test_diagnostic_regex_with_name_defined_error():
    """Test that [name-defined] errors are correctly parsed."""
    line = '/path/to/file.py:2:6:2:7: error: Name "x" is not defined  [name-defined]'

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the name-defined error line"
    assert (
        data["code"] == "name-defined"
    ), f"Expected code 'name-defined', got {data['code']}"
    assert data["message"] == 'Name "x" is not defined'
    assert data["line"] == "2"
    assert data["char"] == "6"
    assert data["end_line"] == "2"
    assert data["end_char"] == "7"


def test_diagnostic_regex_with_note_type():
    """Test that note messages are correctly parsed."""
    line = "/path/to/file.py:5:10: note: See https://mypy.readthedocs.io/en/stable"

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the note line"
    assert data["type"] == "note"
    assert data["message"] == "See https://mypy.readthedocs.io/en/stable"
    assert data["code"] is None


def test_diagnostic_regex_without_column():
    """Test that lines without column numbers are correctly parsed."""
    line = "/path/to/file.py:10: error: Some error without column  [misc]"

    data = _get_group_dict(line)

    assert data is not None, "Regex should match the line without column"
    assert data["code"] == "misc"
    assert data["message"] == "Some error without column"
    assert data["line"] == "10"
    assert data["char"] is None
    assert data["end_line"] is None
    assert data["end_char"] is None
