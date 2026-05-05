// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { Disposable, LogOutputChannel } from 'vscode';
import { LanguageClient } from 'vscode-languageclient/node';
import { IBaseSettings, PythonEnvironmentsProvider, restartServer as _restartServer } from '@vscode/common-python-lsp';
import { MYPY_TOOL_CONFIG } from './constants';
import { traceError } from './logging';
import { ISettings } from './settings';

export type IInitOptions = { settings: ISettings[]; globalSettings: ISettings };

let _disposables: Disposable[] = [];
let _pythonProvider: PythonEnvironmentsProvider | undefined;

function getPythonProvider(): PythonEnvironmentsProvider {
    if (!_pythonProvider) {
        _pythonProvider = new PythonEnvironmentsProvider(MYPY_TOOL_CONFIG);
    }
    return _pythonProvider;
}

export async function restartServer(
    workspaceSetting: ISettings,
    serverId: string,
    serverName: string,
    outputChannel: LogOutputChannel,
    oldLsClient?: LanguageClient,
): Promise<LanguageClient | undefined> {
    _disposables.forEach((d) => {
        try {
            d.dispose();
        } catch (ex) {
            traceError(`Failed to dispose: ${ex}`);
        }
    });
    _disposables = [];

    const result = await _restartServer(
        {
            settings: workspaceSetting as unknown as IBaseSettings,
            serverId,
            serverName,
            outputChannel,
            toolConfig: MYPY_TOOL_CONFIG,
            pythonProvider: getPythonProvider(),
        },
        oldLsClient as any,
    );

    _disposables = result.disposables;
    return result.client as unknown as LanguageClient | undefined;
}
