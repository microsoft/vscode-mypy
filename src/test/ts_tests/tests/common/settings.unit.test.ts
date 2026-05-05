// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// NOTE: Variable resolution and getWorkspaceSettings tests live in the shared
// package (@vscode/common-python-lsp) test suite. Extension-level tests focus
// on extension-specific wrapper behavior.

import { assert } from 'chai';
import * as sinon from 'sinon';
import { checkIfConfigurationChanged } from '../../../../common/settings';

suite('Settings Tests', () => {
    suite('checkIfConfigurationChanged tests', () => {
        teardown(() => {
            sinon.restore();
        });

        test('detects tracked setting changes', () => {
            const event = {
                affectsConfiguration: (section: string) => section === 'mypy.args',
            } as any;
            const result = checkIfConfigurationChanged(event, 'mypy');
            assert.isTrue(result);
        });

        test('detects reportingScope changes', () => {
            const event = {
                affectsConfiguration: (section: string) => section === 'mypy.reportingScope',
            } as any;
            const result = checkIfConfigurationChanged(event, 'mypy');
            assert.isTrue(result);
        });

        test('returns false when unrelated setting changes', () => {
            const event = {
                affectsConfiguration: (_section: string) => false,
            } as any;
            const result = checkIfConfigurationChanged(event, 'mypy');
            assert.isFalse(result);
        });
    });
});
