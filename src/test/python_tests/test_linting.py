# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for linting over LSP.
"""

import copy
import sys
from threading import Event

import pytest
from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, defaults, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_server_info_defaults()
TIMEOUT = 30  # 30 seconds


def test_publish_diagnostics_on_open():
    """Test to ensure linting on file open."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize()

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        def _log_handler(params):
            print(params)

        ls_session.set_notification_callback(session.WINDOW_LOG_MESSAGE, _log_handler)
        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 2, "character": 6},
                    "end": {
                        "line": 2,
                        "character": 7 if sys.version_info >= (3, 8) else 6,
                    },
                },
                "message": 'Name "x" is not defined',
                "severity": 1,
                "code": "name-defined",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-name-defined"
                },
                "source": "Mypy",
            },
            {
                "range": {
                    "start": {"line": 6, "character": 21},
                    "end": {
                        "line": 6,
                        "character": 33 if sys.version_info >= (3, 8) else 21,
                    },
                },
                "message": 'Argument 1 of "__eq__" is incompatible with supertype "object"; supertype defines the argument type as "object"',
                "severity": 1,
                "code": "override",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-override"
                },
                "source": "Mypy",
            },
            {
                "range": {
                    "start": {"line": 6, "character": 21},
                    "end": {
                        "line": 6,
                        "character": 33 if sys.version_info >= (3, 8) else 21,
                    },
                },
                "message": """This violates the Liskov substitution principle
See https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides
It is recommended for "__eq__" to work with arbitrary objects, for example:
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Foo):
            return NotImplemented
        return <logic to compare two Foo instances>""",
                "severity": 3,
                "code": "note",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides"
                },
                "source": "Mypy",
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_save():
    """Test to ensure linting on file save."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize()

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        def _log_handler(params):
            print(params)

        ls_session.set_notification_callback(session.WINDOW_LOG_MESSAGE, _log_handler)
        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_save(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 2, "character": 6},
                    "end": {
                        "line": 2,
                        "character": 7 if sys.version_info >= (3, 8) else 6,
                    },
                },
                "message": 'Name "x" is not defined',
                "severity": 1,
                "code": "name-defined",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-name-defined"
                },
                "source": "Mypy",
            },
            {
                "range": {
                    "start": {"line": 6, "character": 21},
                    "end": {
                        "line": 6,
                        "character": 33 if sys.version_info >= (3, 8) else 21,
                    },
                },
                "message": 'Argument 1 of "__eq__" is incompatible with supertype "object"; supertype defines the argument type as "object"',
                "severity": 1,
                "code": "override",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-override"
                },
                "source": "Mypy",
            },
            {
                "range": {
                    "start": {"line": 6, "character": 21},
                    "end": {
                        "line": 6,
                        "character": 33 if sys.version_info >= (3, 8) else 21,
                    },
                },
                "message": """This violates the Liskov substitution principle
See https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides
It is recommended for "__eq__" to work with arbitrary objects, for example:
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Foo):
            return NotImplemented
        return <logic to compare two Foo instances>""",
                "severity": 3,
                "code": "note",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides"
                },
                "source": "Mypy",
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_close():
    """Test to ensure diagnostic clean-up on file close."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize()

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        def _log_handler(params):
            print(params)

        ls_session.set_notification_callback(session.WINDOW_LOG_MESSAGE, _log_handler)
        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

        # We should receive some diagnostics
        assert_that(len(actual), is_(greater_than(0)))

        # reset waiting
        done.clear()

        ls_session.notify_did_close(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

    # On close should clearout everything
    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [],
    }
    assert_that(actual, is_(expected))


@pytest.mark.parametrize("lint_code", ["name-defined"])
def test_severity_setting(lint_code):
    """Test to ensure linting on file open."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        init_args = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
        init_options = init_args["initializationOptions"]
        init_options["settings"][0]["severity"][lint_code] = "Warning"
        ls_session.initialize(init_args)

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        def _log_handler(params):
            print(params)

        ls_session.set_notification_callback(session.WINDOW_LOG_MESSAGE, _log_handler)
        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 2, "character": 6},
                    "end": {
                        "line": 2,
                        "character": 7 if sys.version_info >= (3, 8) else 6,
                    },
                },
                "message": 'Name "x" is not defined',
                "severity": 2,
                "code": "name-defined",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-name-defined"
                },
                "source": "Mypy",
            },
            {
                "range": {
                    "start": {"line": 6, "character": 21},
                    "end": {
                        "line": 6,
                        "character": 33 if sys.version_info >= (3, 8) else 21,
                    },
                },
                "message": 'Argument 1 of "__eq__" is incompatible with supertype "object"; supertype defines the argument type as "object"',
                "severity": 1,
                "code": "override",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-override"
                },
                "source": "Mypy",
            },
            {
                "range": {
                    "start": {"line": 6, "character": 21},
                    "end": {
                        "line": 6,
                        "character": 33 if sys.version_info >= (3, 8) else 21,
                    },
                },
                "message": """This violates the Liskov substitution principle
See https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides
It is recommended for "__eq__" to work with arbitrary objects, for example:
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Foo):
            return NotImplemented
        return <logic to compare two Foo instances>""",
                "severity": 3,
                "code": "note",
                "codeDescription": {
                    "href": "https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides"
                },
                "source": "Mypy",
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_workspace_reporting_scope():
    """Test reports are generated from multiple files."""
    TEST_FILE2_PATH = constants.TEST_DATA / "sample1" / "sample2.py"
    TEST_FILE2_URI = utils.as_uri(str(TEST_FILE2_PATH))
    contents = TEST_FILE2_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        init_args = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
        init_options = init_args["initializationOptions"]
        init_options["settings"][0]["reportingScope"] = "workspace"
        ls_session.initialize(init_args)

        done = Event()

        def _handler(params):
            params["uri"] = utils.normalizecase(params["uri"])
            actual.append(params)
            if len(actual) == 2:
                done.set()

        def _log_handler(params):
            print(params)

        ls_session.set_notification_callback(session.WINDOW_LOG_MESSAGE, _log_handler)
        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE2_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

        expected = [
            {
                "uri": TEST_FILE_URI,
                "diagnostics": [
                    {
                        "range": {
                            "start": {"line": 2, "character": 6},
                            "end": {
                                "line": 2,
                                "character": 7 if sys.version_info >= (3, 8) else 6,
                            },
                        },
                        "message": 'Name "x" is not defined',
                        "severity": 1,
                        "code": "name-defined",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-name-defined"
                        },
                        "source": "Mypy",
                    },
                    {
                        "range": {
                            "start": {"line": 6, "character": 21},
                            "end": {
                                "line": 6,
                                "character": 33 if sys.version_info >= (3, 8) else 21,
                            },
                        },
                        "message": 'Argument 1 of "__eq__" is incompatible with supertype "object"; supertype defines the argument type as "object"',
                        "severity": 1,
                        "code": "override",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-override"
                        },
                        "source": "Mypy",
                    },
                    {
                        "range": {
                            "start": {"line": 6, "character": 21},
                            "end": {
                                "line": 6,
                                "character": 33 if sys.version_info >= (3, 8) else 21,
                            },
                        },
                        "message": """This violates the Liskov substitution principle
See https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides
It is recommended for "__eq__" to work with arbitrary objects, for example:
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Foo):
            return NotImplemented
        return <logic to compare two Foo instances>""",
                        "severity": 3,
                        "code": "note",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides"
                        },
                        "source": "Mypy",
                    },
                ],
            },
            {
                "uri": TEST_FILE2_URI,
                "diagnostics": [
                    {
                        "range": {
                            "start": {"line": 2, "character": 9},
                            "end": {
                                "line": 2,
                                "character": 16 if sys.version_info >= (3, 8) else 9,
                            },
                        },
                        "message": 'Incompatible types in assignment (expression has type "str", variable has type "int")',
                        "severity": 1,
                        "code": "assignment",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-assignment"
                        },
                        "source": "Mypy",
                    }
                ],
            },
        ]
        assert_that(actual, is_(expected))


def test_file_with_no_errors_generates_empty_diagnostics():
    """Test that a file with no errors generates an empty diagnostics array. This ensures that errors are cleared out."""
    TEST_FILE3_PATH = constants.TEST_DATA / "sample1" / "sample3.py"
    TEST_FILE3_URI = utils.as_uri(str(TEST_FILE3_PATH))
    contents = TEST_FILE3_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize()

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        def _log_handler(params):
            print(params)

        ls_session.set_notification_callback(session.WINDOW_LOG_MESSAGE, _log_handler)
        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE3_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

        expected = {
            "uri": TEST_FILE3_URI,
            "diagnostics": [],
        }
        assert_that(actual, is_(expected))


def test_file_with_no_errors_generates_empty_diagnostics_workspace_mode():
    """Test that a file with no errors generates an empty diagnostics array. This ensures that errors are cleared out."""
    TEST_FILE2_PATH = constants.TEST_DATA / "sample1" / "sample2.py"
    TEST_FILE2_URI = utils.as_uri(str(TEST_FILE2_PATH))
    TEST_FILE3_PATH = constants.TEST_DATA / "sample1" / "sample3.py"
    TEST_FILE3_URI = utils.as_uri(str(TEST_FILE3_PATH))
    contents = TEST_FILE3_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        init_args = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
        init_options = init_args["initializationOptions"]
        init_options["settings"][0]["reportingScope"] = "workspace"
        ls_session.initialize(init_args)

        done = Event()

        def _handler(params):
            params["uri"] = utils.normalizecase(params["uri"])
            actual.append(params)
            if len(actual) == 2:
                done.set()

        def _log_handler(params):
            print(params)

        ls_session.set_notification_callback(session.WINDOW_LOG_MESSAGE, _log_handler)
        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE3_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        assert done.wait(TIMEOUT), "Timed out waiting for diagnostics"

        expected = expected = [
            {
                "uri": TEST_FILE_URI,
                "diagnostics": [
                    {
                        "range": {
                            "start": {"line": 2, "character": 6},
                            "end": {
                                "line": 2,
                                "character": 7 if sys.version_info >= (3, 8) else 6,
                            },
                        },
                        "message": 'Name "x" is not defined',
                        "severity": 1,
                        "code": "name-defined",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-name-defined"
                        },
                        "source": "Mypy",
                    },
                    {
                        "range": {
                            "start": {"line": 6, "character": 21},
                            "end": {
                                "line": 6,
                                "character": 33 if sys.version_info >= (3, 8) else 21,
                            },
                        },
                        "message": 'Argument 1 of "__eq__" is incompatible with supertype "object"; supertype defines the argument type as "object"',
                        "severity": 1,
                        "code": "override",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-override"
                        },
                        "source": "Mypy",
                    },
                    {
                        "range": {
                            "start": {"line": 6, "character": 21},
                            "end": {
                                "line": 6,
                                "character": 33 if sys.version_info >= (3, 8) else 21,
                            },
                        },
                        "message": """This violates the Liskov substitution principle
See https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides
It is recommended for "__eq__" to work with arbitrary objects, for example:
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Foo):
            return NotImplemented
        return <logic to compare two Foo instances>""",
                        "severity": 3,
                        "code": "note",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides"
                        },
                        "source": "Mypy",
                    },
                ],
            },
            {
                "uri": TEST_FILE2_URI,
                "diagnostics": [
                    {
                        "range": {
                            "start": {"line": 2, "character": 9},
                            "end": {
                                "line": 2,
                                "character": 16 if sys.version_info >= (3, 8) else 9,
                            },
                        },
                        "message": 'Incompatible types in assignment (expression has type "str", variable has type "int")',
                        "severity": 1,
                        "code": "assignment",
                        "codeDescription": {
                            "href": "https://mypy.readthedocs.io/en/latest/_refs.html#code-assignment"
                        },
                        "source": "Mypy",
                    }
                ],
            },
        ]

        # Only reports diagnostics on files that have problems
        assert_that(actual, is_(expected))
