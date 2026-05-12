# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for the get_cwd() helper in lsp_server."""

import os
import pathlib
import tempfile
import types

import lsp_server
import pytest

WORKSPACE = "/home/user/myproject"


def _make_settings(cwd=None):
    s = {"workspaceFS": WORKSPACE}
    if cwd is not None:
        s["cwd"] = cwd
    return s


def _make_doc(path):
    return types.SimpleNamespace(path=path)


# ---------------------------------------------------------------------------
# No-document (fallback) cases
# ---------------------------------------------------------------------------


def test_no_cwd_no_document_returns_workspace():
    """When neither cwd nor document is provided, return workspaceFS."""
    settings = _make_settings()
    assert lsp_server.get_cwd(settings, None) == WORKSPACE


def test_plain_cwd_no_document_returned_unchanged():
    """A cwd without variables is returned as-is even without a document."""
    settings = _make_settings(cwd="/custom/path")
    assert lsp_server.get_cwd(settings, None) == "/custom/path"


def test_file_variable_no_document_falls_back_to_workspace():
    """Unresolvable ${file*} variable with no document falls back to workspaceFS."""
    for token in [
        "${file}",
        "${fileBasename}",
        "${fileBasenameNoExtension}",
        "${fileExtname}",
        "${fileDirname}",
        "${fileDirnameBasename}",
        "${fileWorkspaceFolder}",
    ]:
        settings = _make_settings(cwd=token + "/extra")
        assert lsp_server.get_cwd(settings, None) == WORKSPACE, f"Failed for {token}"


def test_relative_file_variable_no_document_falls_back_to_workspace():
    """Unresolvable ${relativeFile*} variable with no document falls back to workspaceFS."""
    for token in ["${relativeFile}", "${relativeFileDirname}"]:
        settings = _make_settings(cwd=token)
        assert lsp_server.get_cwd(settings, None) == WORKSPACE, f"Failed for {token}"


# ---------------------------------------------------------------------------
# With document
# ---------------------------------------------------------------------------

DOC_PATH = "/home/user/myproject/src/foo.py"
DOC = _make_doc(DOC_PATH)


@pytest.mark.parametrize(
    "token, expected",
    [
        pytest.param("${file}", DOC_PATH, id="file"),
        pytest.param("${fileBasename}", "foo.py", id="fileBasename"),
        pytest.param("${fileBasenameNoExtension}", "foo", id="fileBasenameNoExtension"),
        pytest.param("${fileExtname}", ".py", id="fileExtname"),
        pytest.param("${fileDirname}", "/home/user/myproject/src", id="fileDirname"),
        pytest.param("${fileDirnameBasename}", "src", id="fileDirnameBasename"),
        pytest.param(
            "${relativeFile}",
            os.path.relpath(DOC_PATH, WORKSPACE),
            id="relativeFile",
        ),
        pytest.param(
            "${relativeFileDirname}",
            os.path.relpath("/home/user/myproject/src", WORKSPACE),
            id="relativeFileDirname",
        ),
        pytest.param("${fileWorkspaceFolder}", WORKSPACE, id="fileWorkspaceFolder"),
    ],
)
def test_single_variable_resolved(token, expected):
    """Each VS Code variable token resolves to its expected value."""
    settings = _make_settings(cwd=token)
    assert lsp_server.get_cwd(settings, DOC) == expected


def test_composite_pattern_resolved():
    """Variables embedded inside a longer path are substituted correctly."""
    settings = _make_settings(cwd="${fileDirname}/subdir")
    assert lsp_server.get_cwd(settings, DOC) == "/home/user/myproject/src/subdir"


def test_multiple_variables_in_one_cwd():
    """Multiple different variables in the same cwd string are all resolved."""
    settings = _make_settings(cwd="${fileDirname}/${fileBasename}")
    result = lsp_server.get_cwd(settings, DOC)
    assert result == "/home/user/myproject/src/foo.py"


def test_no_variable_in_cwd_unchanged():
    """A cwd with no variables is returned unchanged even when a document exists."""
    settings = _make_settings(cwd="/static/path")
    assert lsp_server.get_cwd(settings, DOC) == "/static/path"


def test_document_with_no_path_falls_back_to_workspace():
    """A document object whose path is falsy triggers the fallback."""
    doc = types.SimpleNamespace(path="")
    settings = _make_settings(cwd="${fileDirname}")
    assert lsp_server.get_cwd(settings, doc) == WORKSPACE


# ---------------------------------------------------------------------------
# mypy-specific: ${nearestConfig}
# ---------------------------------------------------------------------------


def test_nearest_config_no_document_falls_back_to_workspace():
    """${nearestConfig} with no document returns workspaceFS."""
    settings = _make_settings(cwd="${nearestConfig}")
    assert lsp_server.get_cwd(settings, None) == WORKSPACE


def test_nearest_config_finds_config_file():
    """${nearestConfig} finds mypy.ini in parent directory."""
    with tempfile.TemporaryDirectory() as workspace:
        src_dir = os.path.join(workspace, "src")
        os.makedirs(src_dir)
        config_file = os.path.join(workspace, "mypy.ini")
        pathlib.Path(config_file).touch()
        doc_path = os.path.join(src_dir, "foo.py")
        pathlib.Path(doc_path).touch()

        settings = {"workspaceFS": workspace, "cwd": "${nearestConfig}"}
        doc = _make_doc(doc_path)
        result = lsp_server.get_cwd(settings, doc)
        assert result == workspace


def test_nearest_config_falls_back_when_no_config_found():
    """${nearestConfig} returns workspaceFS when no config file is found."""
    with tempfile.TemporaryDirectory() as workspace:
        src_dir = os.path.join(workspace, "src")
        os.makedirs(src_dir)
        doc_path = os.path.join(src_dir, "foo.py")
        pathlib.Path(doc_path).touch()

        settings = {"workspaceFS": workspace, "cwd": "${nearestConfig}"}
        doc = _make_doc(doc_path)
        result = lsp_server.get_cwd(settings, doc)
        assert result == workspace


def test_nearest_config_finds_dot_mypy_ini():
    """${nearestConfig} finds .mypy.ini in parent directory."""
    with tempfile.TemporaryDirectory() as workspace:
        src_dir = os.path.join(workspace, "src")
        os.makedirs(src_dir)
        config_file = os.path.join(workspace, ".mypy.ini")
        pathlib.Path(config_file).touch()
        doc_path = os.path.join(src_dir, "foo.py")
        pathlib.Path(doc_path).touch()

        settings = {"workspaceFS": workspace, "cwd": "${nearestConfig}"}
        doc = _make_doc(doc_path)
        result = lsp_server.get_cwd(settings, doc)
        assert result == workspace


def test_nearest_config_finds_pyproject_toml():
    """${nearestConfig} finds pyproject.toml in parent directory."""
    with tempfile.TemporaryDirectory() as workspace:
        src_dir = os.path.join(workspace, "src")
        os.makedirs(src_dir)
        config_file = os.path.join(workspace, "pyproject.toml")
        pathlib.Path(config_file).touch()
        doc_path = os.path.join(src_dir, "foo.py")
        pathlib.Path(doc_path).touch()

        settings = {"workspaceFS": workspace, "cwd": "${nearestConfig}"}
        doc = _make_doc(doc_path)
        result = lsp_server.get_cwd(settings, doc)
        assert result == workspace


def test_nearest_config_finds_setup_cfg():
    """${nearestConfig} finds setup.cfg in parent directory."""
    with tempfile.TemporaryDirectory() as workspace:
        src_dir = os.path.join(workspace, "src")
        os.makedirs(src_dir)
        config_file = os.path.join(workspace, "setup.cfg")
        pathlib.Path(config_file).touch()
        doc_path = os.path.join(src_dir, "foo.py")
        pathlib.Path(doc_path).touch()

        settings = {"workspaceFS": workspace, "cwd": "${nearestConfig}"}
        doc = _make_doc(doc_path)
        result = lsp_server.get_cwd(settings, doc)
        assert result == workspace


def test_nearest_config_prefers_closest_config():
    """${nearestConfig} picks the nearest directory containing any config file."""
    with tempfile.TemporaryDirectory() as workspace:
        inner = os.path.join(workspace, "pkg")
        src_dir = os.path.join(inner, "sub")
        os.makedirs(src_dir)
        # Place setup.cfg in workspace root and .mypy.ini closer to the doc
        pathlib.Path(os.path.join(workspace, "setup.cfg")).touch()
        pathlib.Path(os.path.join(inner, ".mypy.ini")).touch()
        doc_path = os.path.join(src_dir, "foo.py")
        pathlib.Path(doc_path).touch()

        settings = {"workspaceFS": workspace, "cwd": "${nearestConfig}"}
        doc = _make_doc(doc_path)
        result = lsp_server.get_cwd(settings, doc)
        assert result == inner
