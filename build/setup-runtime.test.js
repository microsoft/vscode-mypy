// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const ts = require('typescript');
const vm = require('node:vm');

function load({ stopping = Promise.resolve() } = {}) {
    const calls = [];
    const toolConfig = {};
    const serverInfo = { name: 'Mypy', module: 'mypy' };
    const exports = {};
    const source = ts.transpileModule(readFileSync(path.join(__dirname, '..', 'src', 'extension.ts'), 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS },
    }).outputText;
    vm.runInNewContext(source, {
        exports,
        require(name) {
            if (name === '../external/vscode-common-python-lsp/typescript/dist') {
                return {
                    loadServerDefaults(root) {
                        calls.push(['defaults', root]);
                        return serverInfo;
                    },
                    activateToolExtension(context, options) {
                        calls.push(['activate', context, options]);
                        return {
                            deactivate() {
                                calls.push(['deactivate']);
                                return stopping;
                            },
                        };
                    },
                };
            }
            if (name === './common/constants') {
                return { EXTENSION_ROOT_DIR: 'extension-root', MYPY_TOOL_CONFIG: toolConfig };
            }
            assert.equal(name, './common/settings');
            return { logLegacySettings: () => calls.push(['legacy']) };
        },
    });
    return { extension: exports, calls, toolConfig, serverInfo };
}

test('passes existing Mypy policy to the facade and logs legacy settings after logger setup', async () => {
    const { extension, calls, toolConfig, serverInfo } = load();
    const context = { subscriptions: [{ dispose() {} }] };
    await extension.activate(context);
    assert.deepEqual(
        calls.map(([kind]) => kind),
        ['defaults', 'activate', 'legacy'],
    );
    assert.equal(calls[0][1], 'extension-root');
    assert.equal(calls[1][1], context);
    assert.equal(calls[1][2].serverInfo, serverInfo);
    assert.equal(calls[1][2].toolConfig, toolConfig);
    assert.equal(calls[1][2].hooks, undefined);
    assert.equal(context.subscriptions.length, 1);
});

test('deactivation waits for the runtime and releases the handle', async () => {
    let finish;
    const stopping = new Promise((resolve) => {
        finish = resolve;
    });
    const { extension, calls } = load({ stopping });
    await extension.activate({ subscriptions: [] });
    let stopped = false;
    const shutdown = extension.deactivate().then(() => {
        stopped = true;
    });
    await Promise.resolve();
    assert.equal(stopped, false);
    finish();
    await shutdown;
    await extension.deactivate();
    assert.equal(calls.filter(([kind]) => kind === 'deactivate').length, 1);
});

test('deactivation before activation is harmless', async () => {
    const { extension, calls } = load();
    await extension.deactivate();
    assert.deepEqual(calls, []);
});
