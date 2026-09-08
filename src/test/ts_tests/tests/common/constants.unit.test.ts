// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as fs from 'fs-extra';
import * as path from 'path';
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
});
