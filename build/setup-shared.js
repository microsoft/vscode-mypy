// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const { spawnSync } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');

function installShared() {
    const cwd = path.resolve(__dirname, '..', 'external', 'vscode-common-python-lsp', 'typescript');
    if (!existsSync(path.join(cwd, 'package.json'))) {
        throw new Error('Shared submodule missing. Run git submodule update --init --recursive before npm ci.');
    }
    const npmCli = process.env.npm_execpath;
    if (!npmCli) {
        throw new Error('Install dependencies using npm ci.');
    }
    for (const args of [
        ['ci', '--include=dev'],
        ['run', 'build'],
    ]) {
        const result = spawnSync(process.execPath, [npmCli, ...args], { cwd, stdio: 'inherit' });
        if (result.error || result.signal || result.status !== 0) {
            throw new Error(
                `Shared ${args.join(' ')} failed: ${result.error?.message || result.signal || result.status}`,
            );
        }
    }
}

module.exports = { installShared };
