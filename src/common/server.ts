// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as proc from 'child_process';
import * as fsapi from 'fs-extra';
import { Disposable, env, l10n, LanguageStatusSeverity, LogOutputChannel, WorkspaceFolder } from 'vscode';
import { State } from 'vscode-languageclient';
import {
    LanguageClient,
    LanguageClientOptions,
    RevealOutputChannelOn,
    ServerOptions,
} from 'vscode-languageclient/node';
import { DEBUG_SERVER_SCRIPT_PATH, SERVER_SCRIPT_PATH } from './constants';
import { traceError, traceInfo, traceVerbose } from './logging';
import { getDebuggerPath } from './python';
import { getExtensionSettings, getGlobalSettings, ISettings } from './settings';
import { getLSClientTraceLevel } from './utilities';
import { getDocumentSelector } from './vscodeapi';
import { updateStatus } from './status';

export type IInitOptions = { settings: ISettings[]; globalSettings: ISettings };

async function createServer(
    settings: ISettings,
    serverId: string,
    serverName: string,
    outputChannel: LogOutputChannel,
    initializationOptions: IInitOptions,
): Promise<LanguageClient> {
    const command = settings.interpreter[0];
    const cwd = settings.cwd;

    // Set debugger path needed for debugging python code.
    const newEnv = { ...process.env };
    const debuggerPath = await getDebuggerPath();
    const isDebugScript = await fsapi.pathExists(DEBUG_SERVER_SCRIPT_PATH);
    if (newEnv.USE_DEBUGPY && debuggerPath) {
        newEnv.DEBUGPY_PATH = debuggerPath;
    } else {
        newEnv.USE_DEBUGPY = 'False';
    }

    // Set import strategy
    newEnv.LS_IMPORT_STRATEGY = settings.importStrategy;

    // Set notification type
    newEnv.LS_SHOW_NOTIFICATION = settings.showNotifications;

    const args =
        newEnv.USE_DEBUGPY === 'False' || !isDebugScript
            ? settings.interpreter.slice(1).concat([SERVER_SCRIPT_PATH])
            : settings.interpreter.slice(1).concat([DEBUG_SERVER_SCRIPT_PATH]);
    traceInfo(`Server run command: ${[command, ...args].join(' ')}`);

    if (fsapi.existsSync(command)) {
        traceInfo(`Server executable exists: "${command}"`);
    } else {
        traceError(`Server executable does not exist: "${command}"`);
    }

    if (fsapi.existsSync(SERVER_SCRIPT_PATH)) {
        traceInfo(`Server executable exists: "${SERVER_SCRIPT_PATH}"`);
    } else {
        traceError(`Server executable does not exist: "${SERVER_SCRIPT_PATH}"`);
    }

    try {
        const serverOptions: ServerOptions = () =>
            Promise.resolve(proc.spawn(command, args, { cwd, env: newEnv, stdio: ['pipe', 'pipe', 'pipe'] }));

        // Options to control the language client
        const clientOptions: LanguageClientOptions = {
            // Register the server for python documents
            documentSelector: getDocumentSelector(),
            outputChannel: outputChannel,
            traceOutputChannel: outputChannel,
            revealOutputChannelOn: RevealOutputChannelOn.Never,
            initializationOptions,
        };
        return new LanguageClient(serverId, serverName, serverOptions, clientOptions);
    } catch (err) {
        traceError(`Error starting server: ${err}`);
        throw err;
    }
}

let _disposables: Disposable[] = [];
export async function restartServer(
    workspaceSetting: ISettings,
    serverId: string,
    serverName: string,
    outputChannel: LogOutputChannel,
    lsClient?: LanguageClient,
): Promise<LanguageClient | undefined> {
    if (lsClient) {
        traceInfo(`Server: Stop requested`);
        try {
            await lsClient.stop();
        } catch (ex) {
            traceError(`Server: Stop failed: ${ex}`);
        }
        _disposables.forEach((d) => d.dispose());
        _disposables = [];
    }
    updateStatus(undefined, LanguageStatusSeverity.Information, true);

    try {
        const newLSClient = await createServer(workspaceSetting, serverId, serverName, outputChannel, {
            settings: await getExtensionSettings(serverId, true),
            globalSettings: await getGlobalSettings(serverId, false),
        });
        traceInfo(`Server: Start requested.`);
        _disposables.push(
            newLSClient.onDidChangeState((e) => {
                switch (e.newState) {
                    case State.Stopped:
                        traceVerbose(`Server State: Stopped`);
                        break;
                    case State.Starting:
                        traceVerbose(`Server State: Starting`);
                        break;
                    case State.Running:
                        traceVerbose(`Server State: Running`);
                        updateStatus(undefined, LanguageStatusSeverity.Information, false);
                        break;
                }
            }),
        );
        await newLSClient.start();
        await newLSClient.setTrace(getLSClientTraceLevel(outputChannel.logLevel, env.logLevel));
        return newLSClient;
    } catch (ex) {
        updateStatus(l10n.t('Server failed to start.'), LanguageStatusSeverity.Error);
        traceError(`Server: Start failed: ${ex}`);
    }
}
