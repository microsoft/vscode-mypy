// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

function load({ missing = false, failure, failAt = 1, npmCli = 'npm-cli.js' } = {}) {
    const calls = [];
    const checked = [];
    const module = { exports: {} };
    vm.runInNewContext(readFileSync(path.join(__dirname, 'setup-shared.js'), 'utf8'), {
        __dirname,
        module,
        process: { execPath: process.execPath, env: { npm_execpath: npmCli } },
        require(name) {
            if (name === 'node:path') {
                return path;
            }
            if (name === 'node:fs') {
                return {
                    existsSync(file) {
                        checked.push(file);
                        return !missing;
                    },
                };
            }
            assert.equal(name, 'node:child_process');
            return {
                spawnSync(command, args, options) {
                    calls.push({ command, args: Array.from(args), ...options });
                    return calls.length === failAt && failure ? failure : { status: 0 };
                },
            };
        },
    });
    return { installShared: module.exports.installShared, calls, checked };
}

test('a failed shared build fails the install even after dependency installation succeeded', () => {
    const { installShared, calls } = load({ failure: { status: 1 }, failAt: 2 });
    assert.throws(installShared, /Shared run build failed/);
    assert.equal(calls.length, 2);
});

test('installs the pinned shared lock and rebuilds without trusting existing dist', () => {
    const { installShared, calls, checked } = load();
    installShared();
    assert.deepEqual(
        calls.map(({ command, args }) => [command, args]),
        [
            [process.execPath, ['npm-cli.js', 'ci', '--include=dev']],
            [process.execPath, ['npm-cli.js', 'run', 'build']],
        ],
    );
    const shared = path.resolve(__dirname, '..', 'external', 'vscode-common-python-lsp', 'typescript');
    assert.deepEqual(checked, [path.join(shared, 'package.json')]);
    for (const call of calls) {
        assert.equal(call.cwd, shared);
        assert.equal(call.stdio, 'inherit');
        assert.equal(call.shell, undefined);
    }
});

test('missing submodule fails instead of silently skipping the runtime build', () => {
    const { installShared, calls } = load({ missing: true });
    assert.throws(installShared, /git submodule update/);
    assert.equal(calls.length, 0);
});

test('requires the npm CLI rather than invoking a platform-specific shell', () => {
    const { installShared, calls } = load({ npmCli: '' });
    assert.throws(installShared, /npm ci/);
    assert.equal(calls.length, 0);
});

for (const failure of [{ status: 7 }, { signal: 'SIGTERM' }, { error: new Error('not found') }]) {
    test(`failed shared install stops before building: ${failure.status || failure.signal || failure.error.message}`, () => {
        const { installShared, calls } = load({ failure });
        assert.throws(installShared, /Shared ci --include=dev failed/);
        assert.equal(calls.length, 1);
    });
}
