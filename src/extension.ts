// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import {
    createToolContext,
    deactivateServer,
    loadServerDefaults,
    PythonEnvironmentsProvider,
    registerCommonSubscriptions,
    registerLogger,
    ToolExtensionContext,
} from '@vscode/common-python-lsp';
import { EXTENSION_ROOT_DIR, MYPY_TOOL_CONFIG } from './common/constants';
import { logLegacySettings } from './common/settings';

let toolContext: ToolExtensionContext | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const serverInfo = loadServerDefaults(EXTENSION_ROOT_DIR);
    const outputChannel = vscode.window.createOutputChannel(serverInfo.name, { log: true });
    context.subscriptions.push(outputChannel, registerLogger(outputChannel));

    const pythonProvider = new PythonEnvironmentsProvider(MYPY_TOOL_CONFIG);
    context.subscriptions.push(pythonProvider);

    toolContext = createToolContext({ serverInfo, outputChannel, toolConfig: MYPY_TOOL_CONFIG, pythonProvider });
    context.subscriptions.push({ dispose: () => toolContext?.dispose() });

    registerCommonSubscriptions(context, {
        serverInfo,
        outputChannel,
        toolConfig: MYPY_TOOL_CONFIG,
        toolContext,
        pythonProvider,
    });

    logLegacySettings();

    setImmediate(() => toolContext!.initialize(context.subscriptions));
}

export async function deactivate(): Promise<void> {
    await deactivateServer(toolContext);
}
