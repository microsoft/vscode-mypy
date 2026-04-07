// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import * as fsapi from 'fs-extra';
import * as dotenv from 'dotenv';
import { WorkspaceFolder } from 'vscode';
import { getConfiguration } from './vscodeapi';
import { traceInfo, traceWarn } from './logging';

function expandTilde(p: string): string {
    const home = process.env.HOME || process.env.USERPROFILE || '';
    if (p === '~') {
        return home;
    }
    if (p.startsWith('~/') || p.startsWith('~\\')) {
        return path.join(home, p.slice(2));
    }
    return p;
}

export async function getEnvFileVars(workspace: WorkspaceFolder): Promise<Record<string, string>> {
    const config = getConfiguration('python', workspace.uri);
    let envFileSetting = config.get<string>('envFile', '${workspaceFolder}/.env');

    envFileSetting = envFileSetting.replace(/\$\{workspaceFolder\}/g, workspace.uri.fsPath);
    envFileSetting = expandTilde(envFileSetting);

    if (!path.isAbsolute(envFileSetting)) {
        envFileSetting = path.join(workspace.uri.fsPath, envFileSetting);
    }

    if (!(await fsapi.pathExists(envFileSetting))) {
        return {};
    }

    try {
        const content = await fsapi.readFile(envFileSetting, 'utf-8');
        const vars = dotenv.parse(content);
        traceInfo(`Loaded ${Object.keys(vars).length} env vars from ${envFileSetting}`);
        return vars;
    } catch (error) {
        traceWarn(`Failed to read env file ${envFileSetting}: ${error}`);
        return {};
    }
}
