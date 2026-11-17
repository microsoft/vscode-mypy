# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Verify every native bundle path installs the matching shared Python checkout."""

import importlib.util
import pathlib
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location(
    "bundle_noxfile", pathlib.Path(__file__).parents[1] / "noxfile.py"
)
NOXFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NOXFILE)


def test_bundle_installs_shared_checkout_after_locked_requirements():
    session = Mock()
    NOXFILE._install_bundle(session)

    requirements, shared = session.install.call_args_list
    assert requirements.args[-2:] == ("-r", "./requirements.txt")
    assert pathlib.Path(shared.args[-1]) == pathlib.Path(
        "external/vscode-common-python-lsp/python"
    )
    assert shared.args[:2] == ("-t", "./bundled/libs")
    assert "--no-deps" in shared.args
    assert "--upgrade" in shared.args
    session.error.assert_not_called()
