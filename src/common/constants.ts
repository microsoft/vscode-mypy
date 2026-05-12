// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import { resolveExtensionRoot, ToolConfig } from '@vscode/common-python-lsp';

export const EXTENSION_ROOT_DIR = resolveExtensionRoot(__dirname);

export const MYPY_CONFIG_FILES = ['mypy.ini', '.mypy.ini', 'pyproject.toml', 'setup.cfg'];

export const MYPY_TOOL_CONFIG: ToolConfig = {
    toolId: 'mypy-type-checker',
    toolDisplayName: 'Mypy',
    toolModule: 'mypy',
    minimumPythonVersion: { major: 3, minor: 10 },
    configFiles: MYPY_CONFIG_FILES,
    serverScript: path.join(EXTENSION_ROOT_DIR, 'bundled', 'tool', 'lsp_server.py'),
    debugServerScript: path.join(EXTENSION_ROOT_DIR, 'bundled', 'tool', '_debug_server.py'),
    settingsDefaults: {
        ignorePatterns: [],
        extraPaths: [],
        reportingScope: 'file',
        preferDaemon: false,
        severity: { error: 'Error', note: 'Information' },
    },
    trackedSettings: [
        'args',
        'cwd',
        'severity',
        'path',
        'interpreter',
        'importStrategy',
        'showNotifications',
        'reportingScope',
        'preferDaemon',
        'ignorePatterns',
        'daemonStatusFile',
        'extraPaths',
    ],
};
