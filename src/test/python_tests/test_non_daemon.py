# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Tests for non-daemon mode"""
from threading import Event
from typing import Any, Dict, List

from hamcrest import (
    assert_that,
    contains_string,
    greater_than,
    has_item,
    has_length,
    is_,
    not_,
)

from .lsp_test_client import constants, defaults, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
TIMEOUT = 30  # 30 seconds


def test_daemon_non_daemon_equivalence_for_file_with_errors():
    """Test that the results of mypy and dmypy are the same for a file with errors."""
    TEST_FILE1_PATH = constants.TEST_DATA / "sample1" / "sample.py"
    contents = TEST_FILE1_PATH.read_text(encoding="utf-8")

    def run(prefer_daemon: bool):
        default_init = defaults.vscode_initialize_defaults()
        default_init["initializationOptions"]["settings"][0][
            "preferDaemon"
        ] = prefer_daemon

        result: Dict[str, Any] = {}
        log_messages: List[str] = []
        with session.LspSession() as ls_session:
            ls_session.initialize(default_init)

            done = Event()

            def _handler(params):
                nonlocal result
                result = params
                done.set()

            def _log_handler(params: Dict[str, str]):
                if params["type"] == 4:  # == lsprotocol.types.MessageType.Log
                    log_messages.append(params["message"])

            ls_session.set_notification_callback(
                session.WINDOW_LOG_MESSAGE, _log_handler
            )
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

        return result, log_messages

    dmypy_result, dmypy_logs = run(True)
    mypy_result, mypy_logs = run(False)
    # Check the consistenty and the sanity of the two results
    assert_that(dmypy_result, is_(mypy_result))
    assert_that(dmypy_result["uri"], is_(TEST_FILE_URI))
    assert_that(dmypy_result["diagnostics"], has_length(greater_than(0)))

    # Check that the two procedures were really different
    assert_that(dmypy_logs, has_item(contains_string(" -m mypy.dmypy ")))
    assert_that(dmypy_logs, not_(has_item(contains_string(" -m mypy "))))
    assert_that(mypy_logs, has_item(contains_string(" -m mypy ")))
    assert_that(mypy_logs, not_(has_item(contains_string(" -m mypy.dmypy "))))
