# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for path and interpreter settings.
"""
import sys
from threading import Event
from typing import Dict

from hamcrest import assert_that, is_

from .lsp_test_client import constants, defaults, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
TIMEOUT = 30  # 30 seconds


class CallbackObject:
    """Object that holds results for WINDOW_LOG_MESSAGE to capture argv"""

    def __init__(self):
        self.result = False

    def check_result(self):
        """returns Boolean result"""
        return self.result

    def check_for_argv_duplication(self, argv: Dict[str, str]):
        """checks if argv duplication exists and sets result boolean"""
        if argv["type"] == 4 and argv["message"].find("--from-stdin") >= 0:
            parts = argv["message"].split()
            count = len([x for x in parts if x.startswith("--from-stdin")])
            self.result = count > 1


def test_path():
    """Test linting using mypy bin path set."""

    default_init = defaults.vscode_initialize_defaults()
    default_init["initializationOptions"]["settings"][0]["path"] = [
        sys.executable,
        "-m",
        "mypy",
    ]

    argv_callback_object = CallbackObject()
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = True
    with session.LspSession() as ls_session:
        ls_session.set_notification_callback(
            session.WINDOW_LOG_MESSAGE,
            argv_callback_object.check_for_argv_duplication,
        )

        done = Event()

        def _handler(_params):
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.initialize(default_init)
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
        done.clear()

        # Call this second time to detect arg duplication.
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

        actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))


def test_interpreter():
    """Test linting using specific python path."""
    default_init = defaults.vscode_initialize_defaults()
    default_init["initializationOptions"]["settings"][0]["interpreter"] = ["python"]

    argv_callback_object = CallbackObject()
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = True
    with session.LspSession() as ls_session:
        ls_session.set_notification_callback(
            session.WINDOW_LOG_MESSAGE,
            argv_callback_object.check_for_argv_duplication,
        )

        done = Event()

        def _handler(_params):
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.initialize(default_init)
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
        done.clear()

        # Call this second time to detect arg duplication.
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

        actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))
