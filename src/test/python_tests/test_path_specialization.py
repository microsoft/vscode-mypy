"""
Test for path and interpreter settings.
"""
import copy
from threading import Event
from typing import Dict

from hamcrest import assert_that, is_

from .lsp_test_client import constants, defaults, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
TIMEOUT = 10  # 10 seconds


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
    """Test linting using pylint bin path set."""

    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["path"] = ["pylint"]

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

        ls_session.initialize(init_params)
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
        done.wait(TIMEOUT)
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
        done.wait(TIMEOUT)

        actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))


def test_interpreter():
    """Test linting using specific python path."""
    init_params = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    init_params["initializationOptions"]["settings"][0]["interpreter"] = ["python"]

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

        ls_session.initialize(init_params)
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
        done.wait(TIMEOUT)
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
        done.wait(TIMEOUT)

        actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))
