# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
LSP session client for testing.
"""

import json
import os
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Lock

from . import defaults
from .constants import PROJECT_ROOT

LSP_EXIT_TIMEOUT = 5000


PUBLISH_DIAGNOSTICS = "textDocument/publishDiagnostics"
WINDOW_LOG_MESSAGE = "window/logMessage"
WINDOW_SHOW_MESSAGE = "window/showMessage"


class JsonRpcWriter:
    """Writes JSON-RPC messages with Content-Length headers to a binary stream."""

    def __init__(self, stream):
        self._stream = stream
        self._lock = Lock()

    def write(self, message):
        """Write a JSON-RPC message with Content-Length header."""
        body = json.dumps(message, separators=(',', ':')).encode('utf-8')
        header = f"Content-Length: {len(body)}\r\n\r\n".encode('ascii')
        with self._lock:
            self._stream.write(header)
            self._stream.write(body)
            self._stream.flush()


class JsonRpcReader:
    """Reads Content-Length framed JSON-RPC messages from a binary stream."""

    def __init__(self, stream):
        self._stream = stream

    def listen(self, callback):
        """Read messages and call callback for each parsed message."""
        try:
            while True:
                # Read headers
                headers = {}
                while True:
                    line = self._stream.readline()
                    if not line:
                        return  # EOF
                    line = line.strip()
                    if not line:
                        break  # Empty line signals end of headers
                    if b':' in line:
                        key, value = line.split(b':', 1)
                        headers[key.strip().decode('ascii')] = value.strip().decode('ascii')

                if 'Content-Length' not in headers:
                    continue

                # Read body
                content_length = int(headers['Content-Length'])
                body = self._stream.read(content_length)
                if not body:
                    return  # EOF

                # Parse and dispatch
                try:
                    message = json.loads(body.decode('utf-8'))
                    callback(message)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass  # Ignore malformed messages
        except (IOError, OSError):
            return  # Stream error, exit gracefully


# pylint: disable=too-many-instance-attributes
class LspSession:
    """Send and Receive messages over LSP as a test LS Client."""

    def __init__(self, cwd=None, script=None):
        self.cwd = cwd if cwd else os.getcwd()
        # pylint: disable=consider-using-with
        self._thread_pool = ThreadPoolExecutor()
        self._sub = None
        self._writer = None
        self._reader = None
        self._notification_callbacks = {}
        self._request_futures = {}
        self._request_id = 0
        self._request_id_lock = Lock()
        self.script = (
            script if script else (PROJECT_ROOT / "bundled" / "tool" / "lsp_server.py")
        )

    def __enter__(self):
        """Context manager entrypoint.

        shell=True needed for pytest-cov to work in subprocess.
        """
        # pylint: disable=consider-using-with
        self._sub = subprocess.Popen(
            [sys.executable, str(self.script)],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            bufsize=0,
            cwd=self.cwd,
            env=os.environ,
            shell="WITH_COVERAGE" in os.environ,
        )

        self._writer = JsonRpcWriter(os.fdopen(self._sub.stdin.fileno(), "wb"))
        self._reader = JsonRpcReader(os.fdopen(self._sub.stdout.fileno(), "rb"))
        self._thread_pool.submit(self._reader.listen, self._handle_message)
        return self

    def __exit__(self, typ, value, _tb):
        self.shutdown(True)
        try:
            self._sub.terminate()
        except Exception:  # pylint:disable=broad-except
            pass
        self._thread_pool.shutdown()

    def _next_id(self):
        """Generate next request ID."""
        with self._request_id_lock:
            self._request_id += 1
            return self._request_id

    def _handle_message(self, message):
        """Route incoming JSON-RPC messages."""
        if "id" in message and "method" not in message:
            # Response
            msg_id = message["id"]
            if msg_id in self._request_futures:
                fut = self._request_futures.pop(msg_id)
                if "error" in message:
                    fut.set_exception(Exception(str(message["error"])))
                else:
                    fut.set_result(message.get("result"))
        elif "method" in message and "id" not in message:
            # Notification
            self._handle_notification(message["method"], message.get("params"))
        elif "method" in message and "id" in message:
            # Server-to-client request
            self._writer.write({
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": None
            })

    def _handle_notification(self, notification_name, params):
        """Internal handler for notifications."""
        fut = Future()

        def _handler():
            try:
                callback = self.get_notification_callback(notification_name)
                callback(params)
                fut.set_result(None)
            except Exception as e:  # pylint: disable=broad-except
                fut.set_exception(e)

        self._thread_pool.submit(_handler)
        return fut

    def initialize(
        self,
        initialize_params=None,
        process_server_capabilities=None,
    ):
        """Sends the initialize request to LSP server."""
        if initialize_params is None:
            initialize_params = defaults.vscode_initialize_defaults()
        server_initialized = Event()

        def _after_initialize(fut):
            if process_server_capabilities:
                process_server_capabilities(fut.result())
            self.initialized()
            server_initialized.set()

        self._send_request(
            "initialize",
            params=(
                initialize_params
                if initialize_params is not None
                else defaults.vscode_initialize_defaults()
            ),
            handle_response=_after_initialize,
        )

        server_initialized.wait()

    def initialized(self, initialized_params=None):
        """Sends the initialized notification to LSP server."""
        self._send_notification("initialized", params=(initialized_params or {}))

    def shutdown(self, should_exit, exit_timeout=LSP_EXIT_TIMEOUT):
        """Sends the shutdown request to LSP server."""

        def _after_shutdown(_):
            if should_exit:
                self.exit_lsp(exit_timeout)

        fut = self._send_request("shutdown", handle_response=_after_shutdown)
        return fut.result()

    def exit_lsp(self, exit_timeout=LSP_EXIT_TIMEOUT):
        """Handles LSP server process exit."""
        self._send_notification("exit")
        # Convert timeout from milliseconds to seconds for subprocess.wait()
        timeout_seconds = exit_timeout / 1000
        assert self._sub.wait(timeout_seconds) == 0

    def notify_did_change(self, did_change_params):
        """Sends did change notification to LSP Server."""
        self._send_notification("textDocument/didChange", params=did_change_params)

    def notify_did_save(self, did_save_params):
        """Sends did save notification to LSP Server."""
        self._send_notification("textDocument/didSave", params=did_save_params)

    def notify_did_open(self, did_open_params):
        """Sends did open notification to LSP Server."""
        self._send_notification("textDocument/didOpen", params=did_open_params)

    def notify_did_close(self, did_close_params):
        """Sends did close notification to LSP Server."""
        self._send_notification("textDocument/didClose", params=did_close_params)

    def text_document_formatting(self, formatting_params):
        """Sends text document format request to LSP server."""
        fut = self._send_request("textDocument/formatting", params=formatting_params)
        return fut.result()

    def text_document_code_action(self, code_action_params):
        """Sends text document code actions request to LSP server."""
        fut = self._send_request("textDocument/codeAction", params=code_action_params)
        return fut.result()

    def code_action_resolve(self, code_action_resolve_params):
        """Sends text document code actions resolve request to LSP server."""
        fut = self._send_request(
            "codeAction/resolve", params=code_action_resolve_params
        )
        return fut.result()

    def set_notification_callback(self, notification_name, callback):
        """Set custom LS notification handler."""
        self._notification_callbacks[notification_name] = callback

    def get_notification_callback(self, notification_name):
        """Gets callback if set or default callback for a given LS
        notification."""
        try:
            return self._notification_callbacks[notification_name]
        except KeyError:

            def _default_handler(_params):
                """Default notification handler."""

            return _default_handler

    def _send_request(self, name, params=None, handle_response=lambda f: f.done()):
        """Sends {name} request to the LSP server."""
        msg_id = self._next_id()
        fut = Future()
        self._request_futures[msg_id] = fut

        message = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": name,
        }
        if params is not None:
            message["params"] = params

        self._writer.write(message)
        fut.add_done_callback(handle_response)
        return fut

    def _send_notification(self, name, params=None):
        """Sends {name} notification to the LSP server."""
        message = {
            "jsonrpc": "2.0",
            "method": name,
        }
        if params is not None:
            message["params"] = params

        self._writer.write(message)
