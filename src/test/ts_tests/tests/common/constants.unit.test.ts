// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as fs from 'fs-extra';
import * as path from 'path';
import * as sinon from 'sinon';
import { Uri, workspace, WorkspaceFolder } from 'vscode';
import { getWorkspaceSettings } from '@vscode/common-python-lsp';
import { EXTENSION_ROOT_DIR, MYPY_TOOL_CONFIG } from '../../../../common/constants';

suite('Mypy tool configuration', () => {
    test('supports per-project environments through a window-scoped opt-in setting', async () => {
        const packageJson = await fs.readJson(path.join(EXTENSION_ROOT_DIR, 'package.json'));
        const setting = packageJson.contributes.configuration.properties['mypy-type-checker.usePerProjectEnvironments'];

        assert.isTrue(MYPY_TOOL_CONFIG.supportsPerProjectEnvironments);
        assert.deepEqual(setting, {
            default: false,
            markdownDescription: '%settings.usePerProjectEnvironments.description%',
            scope: 'window',
            type: 'boolean',
        });
    });

    test('forwards the daemonStatusFile setting to the server', async () => {
        const values: Record<string, unknown> = { daemonStatusFile: '.dmypy.json', preferDaemon: true };
        sinon.stub(workspace, 'getConfiguration').returns({
            get: (key: string, defaultValue?: unknown) => values[key] ?? defaultValue,
            inspect: () => undefined,
        } as never);
        const folder: WorkspaceFolder = { uri: Uri.file(EXTENSION_ROOT_DIR), name: 'workspace', index: 0 };

        try {
            const settings = await getWorkspaceSettings('mypy-type-checker', folder, MYPY_TOOL_CONFIG);

            assert.strictEqual(settings.daemonStatusFile, '.dmypy.json');
        } finally {
            sinon.restore();
        }
    });
});
